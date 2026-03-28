"""
Metrics Aggregator Service

Aggregates success metrics across clients including health scores,
churn predictions, onboarding completion rates, engagement metrics,
and response time averages.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of aggregated metrics."""
    HEALTH_SCORE = "health_score"
    CHURN_PROBABILITY = "churn_probability"
    ONBOARDING_RATE = "onboarding_rate"
    ENGAGEMENT = "engagement"
    RESPONSE_TIME = "response_time"
    ACCURACY = "accuracy"
    RESOLUTION_RATE = "resolution_rate"
    TICKET_VOLUME = "ticket_volume"


@dataclass
class AggregatedMetric:
    """An aggregated metric with statistics."""
    metric_type: MetricType
    total_count: int
    average: float
    median: float
    minimum: float
    maximum: float
    sum_value: float
    std_dev: Optional[float] = None
    percentile_95: Optional[float] = None
    trend: Optional[str] = None  # "up", "down", "stable"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ClientSuccessMetrics:
    """Complete success metrics for all clients."""
    timestamp: datetime
    total_clients: int
    health_metrics: AggregatedMetric
    churn_metrics: AggregatedMetric
    onboarding_metrics: AggregatedMetric
    engagement_metrics: AggregatedMetric
    response_time_metrics: AggregatedMetric
    accuracy_metrics: AggregatedMetric
    resolution_metrics: AggregatedMetric
    by_client: Dict[str, Dict[str, float]]
    at_risk_clients: List[str]
    healthy_clients: List[str]


class MetricsAggregator:
    """
    Aggregate success metrics across all clients.

    Provides:
    - Aggregate health scores across clients
    - Aggregate churn predictions
    - Onboarding completion rates
    - Engagement metrics
    - Response time averages
    """

    # All supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    def __init__(self):
        """Initialize metrics aggregator."""
        self._history: List[ClientSuccessMetrics] = []

    def aggregate_all(
        self,
        health_scores: Optional[Dict[str, float]] = None,
        churn_predictions: Optional[Dict[str, float]] = None,
        onboarding_rates: Optional[Dict[str, float]] = None,
        engagement_scores: Optional[Dict[str, float]] = None,
        response_times: Optional[Dict[str, float]] = None,
        accuracy_rates: Optional[Dict[str, float]] = None,
        resolution_rates: Optional[Dict[str, float]] = None
    ) -> ClientSuccessMetrics:
        """
        Aggregate all success metrics.

        Args:
            health_scores: Dict of client_id to health score (0-100)
            churn_predictions: Dict of client_id to churn probability (0-1)
            onboarding_rates: Dict of client_id to onboarding completion (0-100)
            engagement_scores: Dict of client_id to engagement (0-100)
            response_times: Dict of client_id to avg response time (hours)
            accuracy_rates: Dict of client_id to accuracy (0-100)
            resolution_rates: Dict of client_id to resolution rate (0-100)

        Returns:
            ClientSuccessMetrics with all aggregated data
        """
        # Generate simulated data if not provided
        if health_scores is None:
            health_scores = self._generate_health_scores()
        if churn_predictions is None:
            churn_predictions = self._generate_churn_predictions()
        if onboarding_rates is None:
            onboarding_rates = self._generate_onboarding_rates()
        if engagement_scores is None:
            engagement_scores = self._generate_engagement_scores()
        if response_times is None:
            response_times = self._generate_response_times()
        if accuracy_rates is None:
            accuracy_rates = self._generate_accuracy_rates()
        if resolution_rates is None:
            resolution_rates = self._generate_resolution_rates()

        # Aggregate each metric type
        health_metrics = self._aggregate_metric(
            MetricType.HEALTH_SCORE, list(health_scores.values())
        )
        churn_metrics = self._aggregate_metric(
            MetricType.CHURN_PROBABILITY, list(churn_predictions.values())
        )
        onboarding_metrics = self._aggregate_metric(
            MetricType.ONBOARDING_RATE, list(onboarding_rates.values())
        )
        engagement_metrics = self._aggregate_metric(
            MetricType.ENGAGEMENT, list(engagement_scores.values())
        )
        response_time_metrics = self._aggregate_metric(
            MetricType.RESPONSE_TIME, list(response_times.values())
        )
        accuracy_metrics = self._aggregate_metric(
            MetricType.ACCURACY, list(accuracy_rates.values())
        )
        resolution_metrics = self._aggregate_metric(
            MetricType.RESOLUTION_RATE, list(resolution_rates.values())
        )

        # Combine by client
        by_client = {}
        for client_id in self.SUPPORTED_CLIENTS:
            by_client[client_id] = {
                "health_score": health_scores.get(client_id, 0),
                "churn_probability": churn_predictions.get(client_id, 0),
                "onboarding_rate": onboarding_rates.get(client_id, 0),
                "engagement_score": engagement_scores.get(client_id, 0),
                "response_time": response_times.get(client_id, 0),
                "accuracy_rate": accuracy_rates.get(client_id, 0),
                "resolution_rate": resolution_rates.get(client_id, 0),
            }

        # Identify at-risk and healthy clients
        at_risk = [
            cid for cid, data in by_client.items()
            if data["churn_probability"] > 0.4 or data["health_score"] < 60
        ]
        healthy = [
            cid for cid, data in by_client.items()
            if data["health_score"] >= 80 and data["churn_probability"] < 0.3
        ]

        metrics = ClientSuccessMetrics(
            timestamp=datetime.utcnow(),
            total_clients=len(self.SUPPORTED_CLIENTS),
            health_metrics=health_metrics,
            churn_metrics=churn_metrics,
            onboarding_metrics=onboarding_metrics,
            engagement_metrics=engagement_metrics,
            response_time_metrics=response_time_metrics,
            accuracy_metrics=accuracy_metrics,
            resolution_metrics=resolution_metrics,
            by_client=by_client,
            at_risk_clients=at_risk,
            healthy_clients=healthy,
        )

        # Store in history
        self._history.append(metrics)
        if len(self._history) > 90:
            self._history = self._history[-90:]

        logger.info(f"Aggregated metrics for {metrics.total_clients} clients")
        return metrics

    def _aggregate_metric(
        self,
        metric_type: MetricType,
        values: List[float]
    ) -> AggregatedMetric:
        """Aggregate a list of values into a metric."""
        if not values:
            return AggregatedMetric(
                metric_type=metric_type,
                total_count=0,
                average=0,
                median=0,
                minimum=0,
                maximum=0,
                sum_value=0
            )

        values_sorted = sorted(values)
        n = len(values_sorted)

        avg = sum(values_sorted) / n
        median = values_sorted[n // 2]

        # Standard deviation
        variance = sum((v - avg) ** 2 for v in values_sorted) / n
        std_dev = variance ** 0.5

        # 95th percentile
        p95_idx = int(n * 0.95)
        p95 = values_sorted[min(p95_idx, n - 1)]

        # Determine trend
        trend = self._determine_trend(metric_type)

        return AggregatedMetric(
            metric_type=metric_type,
            total_count=n,
            average=round(avg, 2),
            median=round(median, 2),
            minimum=min(values_sorted),
            maximum=max(values_sorted),
            sum_value=round(sum(values_sorted), 2),
            std_dev=round(std_dev, 2),
            percentile_95=round(p95, 2),
            trend=trend
        )

    def _determine_trend(self, metric_type: MetricType) -> str:
        """Determine trend based on history."""
        if len(self._history) < 2:
            return "stable"

        current = self._history[-1]
        previous = self._history[-2]

        # Get current and previous values based on metric type
        current_val = getattr(current, f"{metric_type.value.split('_')[0]}_metrics", None)
        previous_val = getattr(previous, f"{metric_type.value.split('_')[0]}_metrics", None)

        if current_val and previous_val:
            diff = current_val.average - previous_val.average
            if diff > 2:
                return "up"
            elif diff < -2:
                return "down"

        return "stable"

    # Data generation methods
    def _generate_health_scores(self) -> Dict[str, float]:
        """Generate simulated health scores."""
        import random
        random.seed(42)
        return {
            cid: round(random.uniform(55, 95), 1)
            for cid in self.SUPPORTED_CLIENTS
        }

    def _generate_churn_predictions(self) -> Dict[str, float]:
        """Generate simulated churn predictions."""
        import random
        random.seed(43)
        return {
            cid: round(random.uniform(0.05, 0.45), 3)
            for cid in self.SUPPORTED_CLIENTS
        }

    def _generate_onboarding_rates(self) -> Dict[str, float]:
        """Generate simulated onboarding rates."""
        import random
        random.seed(44)
        return {
            cid: round(random.uniform(50, 100), 1)
            for cid in self.SUPPORTED_CLIENTS
        }

    def _generate_engagement_scores(self) -> Dict[str, float]:
        """Generate simulated engagement scores."""
        import random
        random.seed(45)
        return {
            cid: round(random.uniform(40, 95), 1)
            for cid in self.SUPPORTED_CLIENTS
        }

    def _generate_response_times(self) -> Dict[str, float]:
        """Generate simulated response times."""
        import random
        random.seed(46)
        return {
            cid: round(random.uniform(1.0, 5.0), 2)
            for cid in self.SUPPORTED_CLIENTS
        }

    def _generate_accuracy_rates(self) -> Dict[str, float]:
        """Generate simulated accuracy rates."""
        import random
        random.seed(47)
        return {
            cid: round(random.uniform(70, 98), 1)
            for cid in self.SUPPORTED_CLIENTS
        }

    def _generate_resolution_rates(self) -> Dict[str, float]:
        """Generate simulated resolution rates."""
        import random
        random.seed(48)
        return {
            cid: round(random.uniform(65, 98), 1)
            for cid in self.SUPPORTED_CLIENTS
        }

    def get_client_rankings(
        self,
        metric: str = "health_score"
    ) -> List[Dict[str, Any]]:
        """
        Get clients ranked by a specific metric.

        Args:
            metric: Metric to rank by

        Returns:
            List of dicts with client_id and value, sorted
        """
        if not self._history:
            return []

        latest = self._history[-1]
        rankings = []

        for client_id, data in latest.by_client.items():
            if metric in data:
                rankings.append({
                    "client_id": client_id,
                    "value": data[metric],
                    "rank": 0
                })

        # Sort (descending for most metrics, ascending for churn/response time)
        reverse = metric not in ["churn_probability", "response_time"]
        rankings.sort(key=lambda x: x["value"], reverse=reverse)

        # Assign ranks
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return rankings

    def get_metric_history(
        self,
        metric_type: MetricType,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get historical data for a metric type.

        Args:
            metric_type: Type of metric
            days: Number of days to look back

        Returns:
            List of historical data points
        """
        history = self._history[-days:] if self._history else []
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "average": getattr(m, f"{metric_type.value.split('_')[0]}_metrics").average,
                "total_clients": m.total_clients,
            }
            for m in history
        ]

    def get_summary(self) -> Dict[str, Any]:
        """Get overall summary of all metrics."""
        if not self._history:
            return {"status": "no_data"}

        latest = self._history[-1]

        return {
            "total_clients": latest.total_clients,
            "average_health": latest.health_metrics.average,
            "average_churn_risk": latest.churn_metrics.average,
            "average_onboarding": latest.onboarding_metrics.average,
            "average_engagement": latest.engagement_metrics.average,
            "average_response_time": latest.response_time_metrics.average,
            "average_accuracy": latest.accuracy_metrics.average,
            "at_risk_count": len(latest.at_risk_clients),
            "healthy_count": len(latest.healthy_clients),
            "timestamp": latest.timestamp.isoformat(),
        }

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data formatted for dashboard display."""
        if not self._history:
            return {"status": "no_data"}

        latest = self._history[-1]

        return {
            "summary_cards": {
                "health_score": {
                    "value": latest.health_metrics.average,
                    "trend": latest.health_metrics.trend,
                    "min": latest.health_metrics.minimum,
                    "max": latest.health_metrics.maximum,
                },
                "churn_risk": {
                    "value": latest.churn_metrics.average * 100,  # As percentage
                    "trend": latest.churn_metrics.trend,
                    "at_risk_count": len(latest.at_risk_clients),
                },
                "engagement": {
                    "value": latest.engagement_metrics.average,
                    "trend": latest.engagement_metrics.trend,
                },
                "accuracy": {
                    "value": latest.accuracy_metrics.average,
                    "trend": latest.accuracy_metrics.trend,
                },
            },
            "at_risk_clients": latest.at_risk_clients,
            "healthy_clients": latest.healthy_clients,
            "client_details": latest.by_client,
            "timestamp": latest.timestamp.isoformat(),
        }
