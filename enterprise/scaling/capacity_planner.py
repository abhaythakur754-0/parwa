"""
Capacity Planner Module - Week 52, Builder 3
Capacity planning and forecasting for infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import math

logger = logging.getLogger(__name__)


class PlanningHorizon(Enum):
    """Planning horizon enum"""
    SHORT_TERM = "short_term"  # 1-7 days
    MEDIUM_TERM = "medium_term"  # 1-4 weeks
    LONG_TERM = "long_term"  # 1-12 months


class ResourceType(Enum):
    """Resource type enum"""
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    CONNECTIONS = "connections"


class GrowthModel(Enum):
    """Growth model type"""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    LOGISTIC = "logistic"
    SEASONAL = "seasonal"


@dataclass
class CapacityMetric:
    """Capacity metric data point"""
    resource_type: ResourceType
    current_value: float
    max_capacity: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def utilization_percent(self) -> float:
        """Calculate utilization percentage"""
        if self.max_capacity == 0:
            return 0.0
        return (self.current_value / self.max_capacity) * 100

    @property
    def available_capacity(self) -> float:
        """Calculate available capacity"""
        return max(0, self.max_capacity - self.current_value)


@dataclass
class CapacityThreshold:
    """Capacity threshold configuration"""
    resource_type: ResourceType
    warning_threshold: float = 70.0  # percent
    critical_threshold: float = 85.0  # percent
    max_threshold: float = 95.0  # percent


@dataclass
class CapacityRecommendation:
    """Capacity planning recommendation"""
    resource_type: ResourceType
    action: str
    current_capacity: float
    recommended_capacity: float
    reason: str
    urgency: str  # low, medium, high, critical
    estimated_cost: float = 0.0
    implementation_time: str = ""


@dataclass
class CapacityPlan:
    """Complete capacity plan"""
    horizon: PlanningHorizon
    created_at: datetime = field(default_factory=datetime.utcnow)
    metrics: List[CapacityMetric] = field(default_factory=list)
    recommendations: List[CapacityRecommendation] = field(default_factory=list)
    projections: Dict[str, List[float]] = field(default_factory=dict)
    confidence: float = 0.0


class CapacityAnalyzer:
    """
    Analyzes current capacity and utilization.
    """

    def __init__(self):
        self.metrics_history: Dict[ResourceType, List[CapacityMetric]] = {}
        self.thresholds: Dict[ResourceType, CapacityThreshold] = {}
        self._setup_default_thresholds()

    def _setup_default_thresholds(self) -> None:
        """Setup default thresholds for all resource types"""
        for resource_type in ResourceType:
            self.thresholds[resource_type] = CapacityThreshold(
                resource_type=resource_type
            )

    def set_threshold(
        self,
        resource_type: ResourceType,
        warning: float,
        critical: float,
        max_threshold: float = 95.0,
    ) -> None:
        """Set custom thresholds for a resource"""
        self.thresholds[resource_type] = CapacityThreshold(
            resource_type=resource_type,
            warning_threshold=warning,
            critical_threshold=critical,
            max_threshold=max_threshold,
        )

    def record_metric(
        self,
        resource_type: ResourceType,
        current_value: float,
        max_capacity: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CapacityMetric:
        """Record a capacity metric"""
        metric = CapacityMetric(
            resource_type=resource_type,
            current_value=current_value,
            max_capacity=max_capacity,
            metadata=metadata or {},
        )

        if resource_type not in self.metrics_history:
            self.metrics_history[resource_type] = []
        self.metrics_history[resource_type].append(metric)

        return metric

    def get_current_utilization(
        self,
        resource_type: ResourceType,
    ) -> Optional[float]:
        """Get current utilization for a resource"""
        history = self.metrics_history.get(resource_type, [])
        if history:
            return history[-1].utilization_percent
        return None

    def get_average_utilization(
        self,
        resource_type: ResourceType,
        window: int = 10,
    ) -> Optional[float]:
        """Get average utilization over window"""
        history = self.metrics_history.get(resource_type, [])
        if not history:
            return None
        utils = [m.utilization_percent for m in history[-window:]]
        return sum(utils) / len(utils) if utils else None

    def get_peak_utilization(
        self,
        resource_type: ResourceType,
        window: int = 60,
    ) -> Optional[float]:
        """Get peak utilization over window"""
        history = self.metrics_history.get(resource_type, [])
        if not history:
            return None
        utils = [m.utilization_percent for m in history[-window:]]
        return max(utils) if utils else None

    def check_threshold(
        self,
        resource_type: ResourceType,
    ) -> Tuple[str, float]:
        """Check if resource is approaching threshold"""
        utilization = self.get_current_utilization(resource_type)
        if utilization is None:
            return "unknown", 0.0

        threshold = self.thresholds.get(resource_type)
        if not threshold:
            return "unknown", utilization

        if utilization >= threshold.max_threshold:
            return "max_exceeded", utilization
        elif utilization >= threshold.critical_threshold:
            return "critical", utilization
        elif utilization >= threshold.warning_threshold:
            return "warning", utilization
        return "normal", utilization

    def get_available_capacity(
        self,
        resource_type: ResourceType,
    ) -> Optional[float]:
        """Get available capacity for a resource"""
        history = self.metrics_history.get(resource_type, [])
        if history:
            return history[-1].available_capacity
        return None


class CapacityPlanner:
    """
    Main capacity planning engine.
    """

    def __init__(self):
        self.analyzer = CapacityAnalyzer()
        self.growth_models: Dict[ResourceType, GrowthModel] = {}
        self.plans: List[CapacityPlan] = []
        self.cost_per_unit: Dict[ResourceType, float] = {
            ResourceType.CPU: 0.05,  # per vCPU hour
            ResourceType.MEMORY: 0.01,  # per GB hour
            ResourceType.STORAGE: 0.10,  # per GB month
            ResourceType.NETWORK: 0.05,  # per GB
            ResourceType.CONNECTIONS: 0.001,  # per connection
        }

    def set_growth_model(
        self,
        resource_type: ResourceType,
        model: GrowthModel,
    ) -> None:
        """Set growth model for a resource"""
        self.growth_models[resource_type] = model

    def set_cost_per_unit(
        self,
        resource_type: ResourceType,
        cost: float,
    ) -> None:
        """Set cost per unit for a resource"""
        self.cost_per_unit[resource_type] = cost

    def calculate_growth_rate(
        self,
        resource_type: ResourceType,
        window: int = 30,
    ) -> float:
        """Calculate growth rate based on historical data"""
        history = self.analyzer.metrics_history.get(resource_type, [])
        if len(history) < 2:
            return 0.0

        # Get values from window
        values = [m.current_value for m in history[-window:]]
        if len(values) < 2:
            return 0.0

        # Calculate simple growth rate
        first_val = values[0]
        last_val = values[-1]

        if first_val == 0:
            return 0.0

        return (last_val - first_val) / first_val

    def project_capacity(
        self,
        resource_type: ResourceType,
        days_ahead: int,
        growth_rate: Optional[float] = None,
    ) -> Optional[float]:
        """Project capacity needs for future date"""
        history = self.analyzer.metrics_history.get(resource_type, [])
        if not history:
            return None

        current = history[-1].current_value
        max_capacity = history[-1].max_capacity

        if growth_rate is None:
            growth_rate = self.calculate_growth_rate(resource_type)

        model = self.growth_models.get(resource_type, GrowthModel.LINEAR)

        if model == GrowthModel.LINEAR:
            projected = current * (1 + growth_rate * days_ahead / 30)
        elif model == GrowthModel.EXPONENTIAL:
            projected = current * ((1 + growth_rate) ** (days_ahead / 30))
        elif model == GrowthModel.LOGISTIC:
            # Logistic growth with carrying capacity
            carrying_capacity = max_capacity * 0.95
            k = growth_rate * 10  # Growth coefficient
            projected = carrying_capacity / (
                1 + ((carrying_capacity - current) / current) * math.exp(-k * days_ahead / 30)
            )
        else:
            projected = current * (1 + growth_rate * days_ahead / 30)

        return projected

    def generate_recommendations(
        self,
        resource_type: ResourceType,
        horizon: PlanningHorizon = PlanningHorizon.MEDIUM_TERM,
    ) -> List[CapacityRecommendation]:
        """Generate capacity recommendations"""
        recommendations = []

        status, utilization = self.analyzer.check_threshold(resource_type)
        history = self.analyzer.metrics_history.get(resource_type, [])
        if not history:
            return recommendations

        current_capacity = history[-1].max_capacity
        current_value = history[-1].current_value

        # Determine days ahead based on horizon
        days_map = {
            PlanningHorizon.SHORT_TERM: 7,
            PlanningHorizon.MEDIUM_TERM: 30,
            PlanningHorizon.LONG_TERM: 90,
        }
        days_ahead = days_map[horizon]

        # Project future capacity needs
        projected = self.project_capacity(resource_type, days_ahead)
        if projected is None:
            return recommendations

        # Determine urgency
        if status == "max_exceeded":
            urgency = "critical"
        elif status == "critical":
            urgency = "high"
        elif status == "warning":
            urgency = "medium"
        else:
            urgency = "low"

        # Check if we need to scale up
        threshold = self.analyzer.thresholds.get(resource_type)
        if threshold and projected > current_capacity * threshold.critical_threshold / 100:
            # Calculate recommended capacity
            growth_buffer = 1.2  # 20% buffer
            recommended = math.ceil(projected * growth_buffer)

            # Calculate cost
            cost_per_unit = self.cost_per_unit.get(resource_type, 0)
            additional_units = recommended - current_capacity
            estimated_cost = additional_units * cost_per_unit * 24 * days_ahead

            recommendations.append(CapacityRecommendation(
                resource_type=resource_type,
                action="scale_up",
                current_capacity=current_capacity,
                recommended_capacity=recommended,
                reason=f"Projected utilization ({projected:.1f}) will exceed threshold",
                urgency=urgency,
                estimated_cost=estimated_cost,
                implementation_time="1-3 days",
            ))

        # Check if we can scale down
        elif utilization < 30 and projected < current_capacity * 0.5:
            recommended = math.ceil(projected * 1.3)  # 30% buffer

            cost_per_unit = self.cost_per_unit.get(resource_type, 0)
            saved_units = current_capacity - recommended
            estimated_savings = saved_units * cost_per_unit * 24 * days_ahead

            recommendations.append(CapacityRecommendation(
                resource_type=resource_type,
                action="scale_down",
                current_capacity=current_capacity,
                recommended_capacity=recommended,
                reason="Low utilization - opportunity to reduce costs",
                urgency="low",
                estimated_cost=-estimated_savings,  # Negative = savings
                implementation_time="1-2 days",
            ))

        return recommendations

    def create_plan(
        self,
        horizon: PlanningHorizon = PlanningHorizon.MEDIUM_TERM,
    ) -> CapacityPlan:
        """Create a complete capacity plan"""
        plan = CapacityPlan(horizon=horizon)

        # Collect current metrics
        for resource_type in ResourceType:
            history = self.analyzer.metrics_history.get(resource_type, [])
            if history:
                plan.metrics.append(history[-1])

        # Generate recommendations for each resource
        for resource_type in ResourceType:
            recs = self.generate_recommendations(resource_type, horizon)
            plan.recommendations.extend(recs)

        # Generate projections
        days_map = {
            PlanningHorizon.SHORT_TERM: 7,
            PlanningHorizon.MEDIUM_TERM: 30,
            PlanningHorizon.LONG_TERM: 90,
        }
        days = days_map[horizon]

        for resource_type in ResourceType:
            projections = []
            for day in range(0, days + 1, days // 10 or 1):
                proj = self.project_capacity(resource_type, day)
                if proj is not None:
                    projections.append(proj)
            if projections:
                plan.projections[resource_type.value] = projections

        # Calculate confidence based on data availability
        total_resources = len(ResourceType)
        resources_with_data = len([
            rt for rt in ResourceType
            if self.analyzer.metrics_history.get(rt)
        ])
        plan.confidence = resources_with_data / total_resources if total_resources > 0 else 0

        self.plans.append(plan)
        return plan

    def get_planning_summary(self) -> Dict[str, Any]:
        """Get summary of capacity planning status"""
        summary = {
            "resources": {},
            "plans_count": len(self.plans),
        }

        for resource_type in ResourceType:
            util = self.analyzer.get_current_utilization(resource_type)
            status, _ = self.analyzer.check_threshold(resource_type)
            growth = self.calculate_growth_rate(resource_type)

            summary["resources"][resource_type.value] = {
                "current_utilization": util,
                "status": status,
                "growth_rate": growth,
            }

        return summary


class CapacityAlertManager:
    """
    Manages capacity alerts and notifications.
    """

    def __init__(self, planner: CapacityPlanner):
        self.planner = planner
        self.alerts: List[Dict[str, Any]] = []
        self._alert_handlers: List = []

    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check for capacity alerts"""
        new_alerts = []

        for resource_type in ResourceType:
            status, utilization = self.planner.analyzer.check_threshold(resource_type)

            if status in ["critical", "max_exceeded"]:
                alert = {
                    "resource_type": resource_type.value,
                    "status": status,
                    "utilization": utilization,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"{resource_type.value} utilization at {utilization:.1f}% - {status}",
                }
                new_alerts.append(alert)
                self.alerts.append(alert)

        # Notify handlers
        for alert in new_alerts:
            for handler in self._alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Alert handler error: {e}")

        return new_alerts

    def add_handler(self, handler) -> None:
        """Add an alert handler"""
        self._alert_handlers.append(handler)

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts"""
        return [
            a for a in self.alerts
            if a["status"] in ["critical", "max_exceeded"]
        ]
