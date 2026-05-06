"""
Resource Tuner Module - Week 52, Builder 2
Resource tuning and optimization
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging
import math

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Type of resource"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    CONNECTIONS = "connections"
    THREADS = "threads"


class TuningStrategy(Enum):
    """Tuning strategy"""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class ResourceStatus(Enum):
    """Resource status"""
    OPTIMAL = "optimal"
    UNDER_UTILIZED = "under_utilized"
    OVER_UTILIZED = "over_utilized"
    CRITICAL = "critical"


@dataclass
class ResourceUsage:
    """Resource usage data"""
    resource_type: ResourceType
    current: float
    limit: float
    allocated: float = 0.0
    requested: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def utilization_percent(self) -> float:
        """Calculate utilization percentage"""
        if self.limit == 0:
            return 0.0
        return (self.current / self.limit) * 100

    @property
    def allocation_percent(self) -> float:
        """Calculate allocation percentage"""
        if self.limit == 0:
            return 0.0
        return (self.allocated / self.limit) * 100

    @property
    def available(self) -> float:
        """Calculate available resource"""
        return max(0, self.limit - self.current)

    @property
    def status(self) -> ResourceStatus:
        """Determine resource status"""
        util = self.utilization_percent
        if util >= 95:
            return ResourceStatus.CRITICAL
        elif util >= 80:
            return ResourceStatus.OVER_UTILIZED
        elif util <= 20:
            return ResourceStatus.UNDER_UTILIZED
        return ResourceStatus.OPTIMAL


@dataclass
class TuningRecommendation:
    """Resource tuning recommendation"""
    resource_type: ResourceType
    action: str
    current_value: float
    recommended_value: float
    reason: str
    impact: str
    priority: int = 100
    estimated_savings: float = 0.0


@dataclass
class ResourceLimit:
    """Resource limit configuration"""
    resource_type: ResourceType
    soft_limit: float
    hard_limit: float
    current_limit: float
    unit: str = ""
    auto_adjust: bool = True
    min_limit: float = 0.0
    max_limit: float = float("inf")


class ResourceMonitor:
    """
    Monitor resource usage.
    """

    def __init__(self):
        self.usage_history: Dict[ResourceType, List[ResourceUsage]] = {}
        self.limits: Dict[ResourceType, ResourceLimit] = {}
        self._collectors: Dict[ResourceType, Callable[[], float]] = {}

    def set_limit(
        self,
        resource_type: ResourceType,
        soft_limit: float,
        hard_limit: float,
        unit: str = "",
        auto_adjust: bool = True,
    ) -> None:
        """Set resource limits"""
        self.limits[resource_type] = ResourceLimit(
            resource_type=resource_type,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            current_limit=soft_limit,
            unit=unit,
            auto_adjust=auto_adjust,
        )

    def register_collector(
        self,
        resource_type: ResourceType,
        collector: Callable[[], float],
    ) -> None:
        """Register a resource collector"""
        self._collectors[resource_type] = collector

    def record_usage(
        self,
        resource_type: ResourceType,
        current: float,
        allocated: float = 0.0,
        requested: float = 0.0,
    ) -> ResourceUsage:
        """Record resource usage"""
        limit = self.limits.get(resource_type)
        limit_value = limit.current_limit if limit else 100

        usage = ResourceUsage(
            resource_type=resource_type,
            current=current,
            limit=limit_value,
            allocated=allocated,
            requested=requested,
        )

        if resource_type not in self.usage_history:
            self.usage_history[resource_type] = []
        self.usage_history[resource_type].append(usage)

        return usage

    def collect(self) -> Dict[ResourceType, ResourceUsage]:
        """Collect current resource usage from all collectors"""
        results = {}
        for resource_type, collector in self._collectors.items():
            try:
                value = collector()
                usage = self.record_usage(resource_type, value)
                results[resource_type] = usage
            except Exception as e:
                logger.error(f"Collector for {resource_type} failed: {e}")
        return results

    def get_current_usage(self, resource_type: ResourceType) -> Optional[ResourceUsage]:
        """Get current usage for a resource type"""
        history = self.usage_history.get(resource_type, [])
        return history[-1] if history else None

    def get_average_usage(
        self,
        resource_type: ResourceType,
        window: int = 10,
    ) -> Optional[float]:
        """Get average usage over window"""
        history = self.usage_history.get(resource_type, [])
        if not history:
            return None
        values = [u.current for u in history[-window:]]
        return sum(values) / len(values) if values else None

    def get_peak_usage(
        self,
        resource_type: ResourceType,
        window: int = 60,
    ) -> Optional[float]:
        """Get peak usage over window"""
        history = self.usage_history.get(resource_type, [])
        if not history:
            return None
        values = [u.current for u in history[-window:]]
        return max(values) if values else None


class ResourceTuner:
    """
    Resource tuning and optimization.
    """

    def __init__(
        self,
        strategy: TuningStrategy = TuningStrategy.BALANCED,
    ):
        self.strategy = strategy
        self.monitor = ResourceMonitor()
        self.recommendations: List[TuningRecommendation] = []
        self._tuning_history: List[Dict[str, Any]] = []

    def set_strategy(self, strategy: TuningStrategy) -> None:
        """Set tuning strategy"""
        self.strategy = strategy

    def analyze(self) -> List[TuningRecommendation]:
        """Analyze resources and generate recommendations"""
        self.recommendations = []

        for resource_type in ResourceType:
            usage = self.monitor.get_current_usage(resource_type)
            if not usage:
                continue

            if usage.status == ResourceStatus.CRITICAL:
                self._add_critical_recommendation(usage)
            elif usage.status == ResourceStatus.OVER_UTILIZED:
                self._add_over_utilized_recommendation(usage)
            elif usage.status == ResourceStatus.UNDER_UTILIZED:
                self._add_under_utilized_recommendation(usage)

        # Sort by priority
        self.recommendations.sort(key=lambda r: r.priority, reverse=True)
        return self.recommendations

    def _add_critical_recommendation(self, usage: ResourceUsage) -> None:
        """Add recommendation for critical resource"""
        limit = self.monitor.limits.get(usage.resource_type)

        # Suggest increasing limit
        if limit and limit.auto_adjust:
            increase_factor = self._get_increase_factor()
            new_limit = min(
                limit.current_limit * increase_factor,
                limit.max_limit,
            )
            self.recommendations.append(TuningRecommendation(
                resource_type=usage.resource_type,
                action="increase_limit",
                current_value=limit.current_limit,
                recommended_value=new_limit,
                reason=f"Resource is critically over-utilized ({usage.utilization_percent:.1f}%)",
                impact="Prevent service degradation",
                priority=100,
                estimated_savings=0,
            ))

        # Suggest reducing allocation
        self.recommendations.append(TuningRecommendation(
            resource_type=usage.resource_type,
            action="reduce_consumers",
            current_value=usage.current,
            recommended_value=usage.limit * 0.7,
            reason="Critical resource usage - scale down consumers",
            impact="Immediate relief but may affect throughput",
            priority=95,
        ))

    def _add_over_utilized_recommendation(self, usage: ResourceUsage) -> None:
        """Add recommendation for over-utilized resource"""
        limit = self.monitor.limits.get(usage.resource_type)

        if limit and limit.auto_adjust:
            increase_factor = self._get_increase_factor() * 0.5  # Smaller increase
            new_limit = min(
                limit.current_limit * (1 + increase_factor),
                limit.max_limit,
            )
            self.recommendations.append(TuningRecommendation(
                resource_type=usage.resource_type,
                action="increase_limit",
                current_value=limit.current_limit,
                recommended_value=new_limit,
                reason=f"Resource is over-utilized ({usage.utilization_percent:.1f}%)",
                impact="Prevent future critical state",
                priority=80,
            ))

    def _add_under_utilized_recommendation(self, usage: ResourceUsage) -> None:
        """Add recommendation for under-utilized resource"""
        limit = self.monitor.limits.get(usage.resource_type)

        if limit and limit.auto_adjust:
            decrease_factor = self._get_decrease_factor()
            new_limit = max(
                limit.current_limit * decrease_factor,
                limit.min_limit,
            )
            self.recommendations.append(TuningRecommendation(
                resource_type=usage.resource_type,
                action="decrease_limit",
                current_value=limit.current_limit,
                recommended_value=new_limit,
                reason=f"Resource is under-utilized ({usage.utilization_percent:.1f}%)",
                impact="Cost savings",
                priority=50,
                estimated_savings=(limit.current_limit - new_limit) * self._get_cost_per_unit(usage.resource_type),
            ))

    def _get_increase_factor(self) -> float:
        """Get increase factor based on strategy"""
        if self.strategy == TuningStrategy.AGGRESSIVE:
            return 2.0
        elif self.strategy == TuningStrategy.BALANCED:
            return 1.5
        else:  # CONSERVATIVE
            return 1.25

    def _get_decrease_factor(self) -> float:
        """Get decrease factor based on strategy"""
        if self.strategy == TuningStrategy.AGGRESSIVE:
            return 0.5
        elif self.strategy == TuningStrategy.BALANCED:
            return 0.75
        else:  # CONSERVATIVE
            return 0.9

    def _get_cost_per_unit(self, resource_type: ResourceType) -> float:
        """Get cost per unit for a resource (placeholder)"""
        costs = {
            ResourceType.CPU: 0.05,  # per vCPU hour
            ResourceType.MEMORY: 0.01,  # per GB hour
            ResourceType.DISK: 0.10,  # per GB month
            ResourceType.NETWORK: 0.05,  # per GB
            ResourceType.CONNECTIONS: 0.001,  # per connection
            ResourceType.THREADS: 0.0001,  # per thread
        }
        return costs.get(resource_type, 0.0)

    def apply_recommendation(
        self,
        recommendation: TuningRecommendation,
    ) -> bool:
        """Apply a tuning recommendation"""
        try:
            limit = self.monitor.limits.get(recommendation.resource_type)
            if not limit:
                return False

            if recommendation.action == "increase_limit":
                limit.current_limit = recommendation.recommended_value
            elif recommendation.action == "decrease_limit":
                limit.current_limit = recommendation.recommended_value
            else:
                return False

            # Record in history
            self._tuning_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "recommendation": recommendation,
                "applied": True,
            })

            logger.info(
                f"Applied tuning: {recommendation.resource_type.value} "
                f"{recommendation.action} to {recommendation.recommended_value}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to apply recommendation: {e}")
            return False

    def auto_tune(self) -> List[TuningRecommendation]:
        """Automatically apply tuning recommendations"""
        recommendations = self.analyze()
        applied = []

        for rec in recommendations:
            if rec.priority >= 80:  # Only apply high priority
                if self.apply_recommendation(rec):
                    applied.append(rec)

        return applied

    def get_tuning_summary(self) -> Dict[str, Any]:
        """Get summary of resource tuning status"""
        summary = {
            "strategy": self.strategy.value,
            "resources": {},
            "recommendations_count": len(self.recommendations),
            "tuning_history_count": len(self._tuning_history),
        }

        for resource_type in ResourceType:
            usage = self.monitor.get_current_usage(resource_type)
            if usage:
                summary["resources"][resource_type.value] = {
                    "current": usage.current,
                    "limit": usage.limit,
                    "utilization_percent": usage.utilization_percent,
                    "status": usage.status.value,
                }

        return summary


class ThreadPoolTuner(ResourceTuner):
    """
    Thread pool specific tuner.
    """

    def __init__(self, strategy: TuningStrategy = TuningStrategy.BALANCED):
        super().__init__(strategy)
        self.min_threads = 1
        self.max_threads = 100
        self.optimal_utilization = 0.7

    def calculate_optimal_threads(
        self,
        current_threads: int,
        current_utilization: float,
        avg_task_time_ms: float,
        target_utilization: float = None,
    ) -> int:
        """Calculate optimal thread count"""
        target = target_utilization or self.optimal_utilization

        if current_utilization < 0.1:
            # Very low utilization - reduce threads
            return max(self.min_threads, current_threads // 2)

        # Little's Law approximation
        # optimal_threads = arrival_rate * avg_task_time
        # Using utilization as proxy
        if current_utilization > 0:
            optimal = int(current_threads * (current_utilization / target))
            return max(self.min_threads, min(optimal, self.max_threads))

        return current_threads


class ConnectionPoolTuner(ResourceTuner):
    """
    Connection pool specific tuner.
    """

    def __init__(self, strategy: TuningStrategy = TuningStrategy.BALANCED):
        super().__init__(strategy)
        self.min_connections = 5
        self.max_connections = 100
        self.optimal_utilization = 0.8

    def calculate_optimal_connections(
        self,
        current_connections: int,
        active_connections: int,
        wait_queue_size: int,
        avg_query_time_ms: float,
    ) -> int:
        """Calculate optimal connection count"""
        utilization = active_connections / current_connections if current_connections > 0 else 0

        # If there's a wait queue, we need more connections
        if wait_queue_size > 0:
            new_count = current_connections + min(wait_queue_size, 10)
            return min(new_count, self.max_connections)

        # If utilization is very low, reduce connections
        if utilization < 0.3:
            return max(self.min_connections, int(current_connections * 0.7))

        # If utilization is very high but no wait queue, add some headroom
        if utilization > 0.9:
            return min(current_connections + 5, self.max_connections)

        return current_connections
