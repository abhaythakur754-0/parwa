"""Cost Monitoring Service for PARWA.

This module provides cost monitoring capabilities to track
and optimize infrastructure spending across the platform.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class CostMetric:
    """Cost metric data structure."""
    service: str
    resource_type: str
    cost_usd: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class CostAlert:
    """Cost alert configuration."""
    threshold_usd: float
    period_days: int
    recipients: List[str]
    enabled: bool = True


class CostMonitor:
    """Monitor infrastructure costs across services."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize cost monitor."""
        self.config = config or {}
        self.cost_history: List[CostMetric] = []
        self.alerts: List[CostAlert] = []
        self._setup_default_alerts()

    def _setup_default_alerts(self) -> None:
        """Setup default cost alerts."""
        self.alerts = [
            CostAlert(
                threshold_usd=1000.0,
                period_days=7,
                recipients=["finance@parwa.com"],
                enabled=True,
            ),
            CostAlert(
                threshold_usd=5000.0,
                period_days=30,
                recipients=["finance@parwa.com", "ops@parwa.com"],
                enabled=True,
            ),
        ]

    def track_cost(
        self,
        service: str,
        resource_type: str,
        cost_usd: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> CostMetric:
        """Track a cost metric."""
        metric = CostMetric(
            service=service,
            resource_type=resource_type,
            cost_usd=cost_usd,
            timestamp=datetime.now(),
            tags=tags or {},
        )
        self.cost_history.append(metric)
        logger.info(
            f"Tracked cost: {service}/{resource_type} = ${cost_usd:.2f}"
        )
        self._check_alerts()
        return metric

    def get_daily_costs(self, days: int = 7) -> Dict[str, float]:
        """Get daily costs for the past N days."""
        cutoff = datetime.now() - timedelta(days=days)
        daily_costs: Dict[str, float] = {}

        for metric in self.cost_history:
            if metric.timestamp >= cutoff:
                date_key = metric.timestamp.strftime("%Y-%m-%d")
                daily_costs[date_key] = daily_costs.get(date_key, 0) + metric.cost_usd

        return daily_costs

    def get_service_costs(self) -> Dict[str, float]:
        """Get costs grouped by service."""
        service_costs: Dict[str, float] = {}
        for metric in self.cost_history:
            service_costs[metric.service] = service_costs.get(
                metric.service, 0.0
            ) + metric.cost_usd
        return service_costs

    def get_total_cost(self, days: int = 30) -> float:
        """Get total cost for the past N days."""
        cutoff = datetime.now() - timedelta(days=days)
        return sum(
            m.cost_usd for m in self.cost_history if m.timestamp >= cutoff
        )

    def _check_alerts(self) -> None:
        """Check if any cost alerts should trigger."""
        for alert in self.alerts:
            if not alert.enabled:
                continue
            total = self.get_total_cost(alert.period_days)
            if total >= alert.threshold_usd:
                self._send_alert(alert, total)

    def _send_alert(self, alert: CostAlert, current_cost: float) -> None:
        """Send cost alert notification."""
        logger.warning(
            f"Cost alert: ${current_cost:.2f} exceeds ${alert.threshold_usd:.2f} "
            f"over {alert.period_days} days"
        )

    def get_cost_report(self) -> Dict[str, Any]:
        """Generate comprehensive cost report."""
        return {
            "total_7_days": self.get_total_cost(7),
            "total_30_days": self.get_total_cost(30),
            "by_service": self.get_service_costs(),
            "by_day": self.get_daily_costs(7),
            "metrics_count": len(self.cost_history),
        }


class APIUsageTracker:
    """Track API usage costs."""

    def __init__(self):
        """Initialize API usage tracker."""
        self.usage: Dict[str, List[Dict[str, Any]]] = {}

    def track_api_call(
        self,
        api_name: str,
        endpoint: str,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Track an API call."""
        if api_name not in self.usage:
            self.usage[api_name] = []

        self.usage[api_name].append({
            "endpoint": endpoint,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
            "timestamp": datetime.now().isoformat(),
        })

    def get_api_costs(self) -> Dict[str, float]:
        """Get costs grouped by API."""
        api_costs: Dict[str, float] = {}
        for api_name, calls in self.usage.items():
            total = sum(c.get("cost_usd", 0) for c in calls)
            api_costs[api_name] = total
        return api_costs

    def get_token_usage(self) -> Dict[str, int]:
        """Get token usage grouped by API."""
        token_usage: Dict[str, int] = {}
        for api_name, calls in self.usage.items():
            total = sum(c.get("tokens_used", 0) for c in calls)
            token_usage[api_name] = total
        return token_usage


class DatabaseCostTracker:
    """Track database-related costs."""

    def __init__(self):
        """Initialize database cost tracker."""
        self.storage_gb: float = 0.0
        self.compute_hours: float = 0.0
        self.connection_hours: float = 0.0

    def update_storage(self, gb: float) -> None:
        """Update storage usage."""
        self.storage_gb = gb

    def add_compute_hours(self, hours: float) -> None:
        """Add compute hours."""
        self.compute_hours += hours

    def add_connection_hours(self, hours: float) -> None:
        """Add connection hours."""
        self.connection_hours += hours

    def estimate_monthly_cost(self) -> Dict[str, float]:
        """Estimate monthly database costs."""
        # Approximate pricing (varies by provider)
        storage_cost = self.storage_gb * 0.115  # $0.115/GB/month
        compute_cost = self.compute_hours * 0.05  # $0.05/hour
        connection_cost = self.connection_hours * 0.01  # $0.01/hour

        return {
            "storage_usd": storage_cost,
            "compute_usd": compute_cost,
            "connection_usd": connection_cost,
            "total_usd": storage_cost + compute_cost + connection_cost,
        }


def get_cost_monitor() -> CostMonitor:
    """Get singleton cost monitor instance."""
    return CostMonitor()
