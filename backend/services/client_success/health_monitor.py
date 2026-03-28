"""
Health Monitor Service

Monitors client health metrics including activity levels, ticket volumes,
response times, and accuracy metrics. Generates daily health snapshots
for all tracked clients.
"""
from typing import Dict, List, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels for clients."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class HealthMetric:
    """Individual health metric data point."""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trend: Optional[str] = None  # "up", "down", "stable"


@dataclass
class ClientHealthSnapshot:
    """Daily health snapshot for a client."""
    client_id: str
    timestamp: datetime
    activity_level: float  # 0-100
    ticket_volume: int
    avg_response_time: float  # hours
    accuracy_rate: float  # percentage
    resolution_rate: float  # percentage
    engagement_score: float  # 0-100
    overall_health: float  # 0-100
    status: HealthStatus
    metrics: List[HealthMetric] = field(default_factory=list)


class HealthMonitor:
    """
    Monitor client health across all dimensions.

    Tracks activity levels, ticket volumes, response times,
    accuracy metrics, and generates daily health snapshots.
    Supports all 10 clients (client_001 through client_010).
    """

    # All supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    # Health status thresholds
    HEALTH_THRESHOLDS = {
        HealthStatus.EXCELLENT: 90,
        HealthStatus.GOOD: 75,
        HealthStatus.FAIR: 60,
        HealthStatus.POOR: 40,
        HealthStatus.CRITICAL: 0,
    }

    def __init__(self, db_session: Optional[Any] = None):
        """
        Initialize health monitor.

        Args:
            db_session: Optional database session for data queries
        """
        self.db_session = db_session
        self._snapshots: Dict[str, ClientHealthSnapshot] = {}
        self._historical_data: Dict[str, List[ClientHealthSnapshot]] = {
            client: [] for client in self.SUPPORTED_CLIENTS
        }

    async def monitor_all_clients(self) -> Dict[str, ClientHealthSnapshot]:
        """
        Monitor health for all 10 clients.

        Returns:
            Dict mapping client_id to health snapshot
        """
        logger.info("Starting health monitoring for all 10 clients")

        tasks = [
            self.monitor_client(client_id)
            for client_id in self.SUPPORTED_CLIENTS
        ]

        snapshots = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for client_id, snapshot in zip(self.SUPPORTED_CLIENTS, snapshots):
            if isinstance(snapshot, Exception):
                logger.error(f"Error monitoring {client_id}: {snapshot}")
                # Create fallback snapshot
                snapshot = self._create_fallback_snapshot(client_id)
            results[client_id] = snapshot
            self._snapshots[client_id] = snapshot
            self._historical_data[client_id].append(snapshot)
            # Keep last 30 days only
            if len(self._historical_data[client_id]) > 30:
                self._historical_data[client_id].pop(0)

        logger.info(f"Health monitoring complete for {len(results)} clients")
        return results

    async def monitor_client(self, client_id: str) -> ClientHealthSnapshot:
        """
        Monitor health for a single client.

        Args:
            client_id: Client identifier (e.g., "client_001")

        Returns:
            ClientHealthSnapshot with current health metrics
        """
        if client_id not in self.SUPPORTED_CLIENTS:
            raise ValueError(f"Unsupported client: {client_id}")

        # Gather all metrics in parallel
        activity_level = await self._track_activity_level(client_id)
        ticket_volume = await self._monitor_ticket_volume(client_id)
        response_time = await self._track_response_times(client_id)
        accuracy = await self._monitor_accuracy(client_id)
        resolution_rate = await self._track_resolution_rate(client_id)
        engagement = await self._calculate_engagement(client_id)

        # Calculate overall health score
        overall_health = self._calculate_overall_health(
            activity_level=activity_level,
            accuracy=accuracy,
            response_time=response_time,
            resolution_rate=resolution_rate,
            engagement=engagement
        )

        # Determine health status
        status = self._determine_health_status(overall_health)

        # Build metrics list
        metrics = [
            HealthMetric("activity_level", activity_level, "%",
                        trend=self._get_trend(client_id, "activity_level", activity_level)),
            HealthMetric("ticket_volume", float(ticket_volume), "count"),
            HealthMetric("avg_response_time", response_time, "hours",
                        trend=self._get_trend(client_id, "response_time", response_time)),
            HealthMetric("accuracy_rate", accuracy, "%",
                        trend=self._get_trend(client_id, "accuracy", accuracy)),
            HealthMetric("resolution_rate", resolution_rate, "%"),
            HealthMetric("engagement_score", engagement, "%"),
        ]

        snapshot = ClientHealthSnapshot(
            client_id=client_id,
            timestamp=datetime.utcnow(),
            activity_level=activity_level,
            ticket_volume=ticket_volume,
            avg_response_time=response_time,
            accuracy_rate=accuracy,
            resolution_rate=resolution_rate,
            engagement_score=engagement,
            overall_health=overall_health,
            status=status,
            metrics=metrics
        )

        logger.info(f"Health snapshot for {client_id}: {overall_health:.1f}% ({status.value})")
        return snapshot

    async def _track_activity_level(self, client_id: str) -> float:
        """
        Track client activity level (0-100).

        Based on usage frequency, interaction count, and feature adoption.
        """
        # Simulate activity tracking (would query actual usage data)
        base_activity = hash(client_id) % 30 + 50  # 50-80 base range
        variance = (datetime.utcnow().hour % 10) * 2
        return min(100.0, max(0.0, base_activity + variance))

    async def _monitor_ticket_volume(self, client_id: str) -> int:
        """
        Monitor current ticket volume for client.
        """
        # Simulate ticket volume (would query actual ticket data)
        base_volume = hash(client_id) % 20 + 5  # 5-25 tickets
        return base_volume

    async def _track_response_times(self, client_id: str) -> float:
        """
        Track average response time in hours.
        """
        # Simulate response times (would query actual response data)
        base_time = 1.5 + (hash(client_id) % 30) / 10  # 1.5-4.5 hours
        return round(base_time, 2)

    async def _monitor_accuracy(self, client_id: str) -> float:
        """
        Monitor AI accuracy rate for client.
        """
        # Simulate accuracy (would query actual accuracy metrics)
        base_accuracy = 80.0 + (hash(client_id) % 15)  # 80-95%
        return min(100.0, base_accuracy)

    async def _track_resolution_rate(self, client_id: str) -> float:
        """
        Track ticket resolution rate.
        """
        # Simulate resolution rate
        base_rate = 75.0 + (hash(client_id) % 20)  # 75-95%
        return min(100.0, base_rate)

    async def _calculate_engagement(self, client_id: str) -> float:
        """
        Calculate engagement score based on feature usage and interactions.
        """
        # Simulate engagement
        base_engagement = 60.0 + (hash(client_id) % 30)  # 60-90%
        return min(100.0, base_engagement)

    def _calculate_overall_health(
        self,
        activity_level: float,
        accuracy: float,
        response_time: float,
        resolution_rate: float,
        engagement: float
    ) -> float:
        """
        Calculate overall health score using weighted factors.

        Weights:
        - Activity level: 20%
        - Accuracy: 30%
        - Response time: 20% (inverted - lower is better)
        - Resolution rate: 20%
        - Engagement: 10%
        """
        # Normalize response time (target: <2 hours, max: 8 hours)
        response_score = max(0, 100 - (response_time - 2) * 20)

        weighted_score = (
            activity_level * 0.20 +
            accuracy * 0.30 +
            response_score * 0.20 +
            resolution_rate * 0.20 +
            engagement * 0.10
        )

        return round(min(100.0, max(0.0, weighted_score)), 1)

    def _determine_health_status(self, health_score: float) -> HealthStatus:
        """
        Determine health status based on score thresholds.
        """
        if health_score >= self.HEALTH_THRESHOLDS[HealthStatus.EXCELLENT]:
            return HealthStatus.EXCELLENT
        elif health_score >= self.HEALTH_THRESHOLDS[HealthStatus.GOOD]:
            return HealthStatus.GOOD
        elif health_score >= self.HEALTH_THRESHOLDS[HealthStatus.FAIR]:
            return HealthStatus.FAIR
        elif health_score >= self.HEALTH_THRESHOLDS[HealthStatus.POOR]:
            return HealthStatus.POOR
        else:
            return HealthStatus.CRITICAL

    def _get_trend(self, client_id: str, metric_name: str,
                   current_value: float) -> Optional[str]:
        """
        Determine trend direction for a metric.
        """
        history = self._historical_data.get(client_id, [])
        if len(history) < 2:
            return None

        last_snapshot = history[-1]
        previous_value = None

        for metric in last_snapshot.metrics:
            if metric.name == metric_name:
                previous_value = metric.value
                break

        if previous_value is None:
            return None

        diff = current_value - previous_value
        if diff > 2:
            return "up"
        elif diff < -2:
            return "down"
        else:
            return "stable"

    def _create_fallback_snapshot(self, client_id: str) -> ClientHealthSnapshot:
        """
        Create a fallback snapshot when monitoring fails.
        """
        return ClientHealthSnapshot(
            client_id=client_id,
            timestamp=datetime.utcnow(),
            activity_level=50.0,
            ticket_volume=10,
            avg_response_time=3.0,
            accuracy_rate=80.0,
            resolution_rate=75.0,
            engagement_score=60.0,
            overall_health=65.0,
            status=HealthStatus.FAIR,
            metrics=[]
        )

    def get_client_snapshot(self, client_id: str) -> Optional[ClientHealthSnapshot]:
        """
        Get the most recent health snapshot for a client.
        """
        return self._snapshots.get(client_id)

    def get_client_history(self, client_id: str,
                          days: int = 7) -> List[ClientHealthSnapshot]:
        """
        Get historical health snapshots for a client.
        """
        history = self._historical_data.get(client_id, [])
        return history[-days:] if history else []

    def get_all_current_snapshots(self) -> Dict[str, ClientHealthSnapshot]:
        """
        Get current health snapshots for all clients.
        """
        return self._snapshots.copy()

    def get_clients_by_status(self, status: HealthStatus) -> List[str]:
        """
        Get list of clients with a specific health status.
        """
        return [
            client_id for client_id, snapshot in self._snapshots.items()
            if snapshot.status == status
        ]

    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get overall health summary across all clients.
        """
        if not self._snapshots:
            return {"status": "no_data", "clients_monitored": 0}

        scores = [s.overall_health for s in self._snapshots.values()]
        avg_health = sum(scores) / len(scores)

        status_counts = {}
        for status in HealthStatus:
            status_counts[status.value] = len(self.get_clients_by_status(status))

        return {
            "clients_monitored": len(self._snapshots),
            "average_health": round(avg_health, 1),
            "status_distribution": status_counts,
            "critical_clients": self.get_clients_by_status(HealthStatus.CRITICAL),
            "poor_health_clients": self.get_clients_by_status(HealthStatus.POOR),
        }
