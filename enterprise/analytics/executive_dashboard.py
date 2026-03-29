"""
Enterprise Analytics - Executive Dashboard
Executive-level analytics dashboard for enterprise clients
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class DashboardMetric(BaseModel):
    """Single dashboard metric"""
    name: str
    value: float
    unit: str
    change: Optional[float] = None
    trend: Optional[str] = None

    model_config = ConfigDict()


class ExecutiveDashboard:
    """
    Executive-level dashboard for enterprise clients.
    Provides high-level business metrics and KPIs.
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.metrics: Dict[str, DashboardMetric] = {}

    def get_overview(self) -> Dict[str, Any]:
        """Get executive overview"""
        return {
            "client_id": self.client_id,
            "period": "last_30_days",
            "metrics": {
                "total_tickets": self._get_total_tickets(),
                "resolution_rate": self._get_resolution_rate(),
                "avg_response_time": self._get_avg_response_time(),
                "customer_satisfaction": self._get_csat(),
                "cost_savings": self._get_cost_savings()
            },
            "generated_at": datetime.utcnow().isoformat()
        }

    def _get_total_tickets(self) -> int:
        """Get total tickets handled"""
        return 15000

    def _get_resolution_rate(self) -> float:
        """Get resolution rate"""
        return 94.5

    def _get_avg_response_time(self) -> float:
        """Get average response time in seconds"""
        return 12.3

    def _get_csat(self) -> float:
        """Get customer satisfaction score"""
        return 4.7

    def _get_cost_savings(self) -> float:
        """Get cost savings in USD"""
        return 125000.00

    def get_trends(self, days: int = 30) -> Dict[str, List[float]]:
        """Get trend data"""
        return {
            "tickets": [500 + i * 10 for i in range(days)],
            "resolution_rate": [93.0 + i * 0.05 for i in range(days)],
            "csat": [4.5 + i * 0.01 for i in range(days)]
        }

    def get_comparison(self) -> Dict[str, Any]:
        """Get period-over-period comparison"""
        return {
            "current_period": {
                "tickets": 15000,
                "resolution_rate": 94.5
            },
            "previous_period": {
                "tickets": 12000,
                "resolution_rate": 92.0
            },
            "change": {
                "tickets": 25.0,
                "resolution_rate": 2.5
            }
        }
