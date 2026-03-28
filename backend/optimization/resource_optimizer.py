"""Resource Optimizer for PARWA.

This module provides resource optimization recommendations
to improve efficiency and reduce costs.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptimizationRecommendation:
    """Resource optimization recommendation."""
    resource_type: str
    resource_name: str
    current_value: Any
    recommended_value: Any
    potential_savings_usd: float
    priority: str  # high, medium, low
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ResourceUsage:
    """Resource usage metrics."""
    resource_name: str
    resource_type: str
    cpu_usage_percent: float
    memory_usage_percent: float
    cpu_request: float  # cores
    memory_request: float  # GB
    cpu_limit: float
    memory_limit: float
    cost_usd_per_hour: float


class ResourceOptimizer:
    """Optimize resource allocation for efficiency."""

    # Thresholds for optimization
    CPU_UNDERUTILIZED_THRESHOLD = 30.0  # %
    CPU_OVERUTILIZED_THRESHOLD = 85.0  # %
    MEMORY_UNDERUTILIZED_THRESHOLD = 30.0  # %
    MEMORY_OVERUTILIZED_THRESHOLD = 85.0  # %

    def __init__(self):
        """Initialize resource optimizer."""
        self.resources: Dict[str, ResourceUsage] = {}
        self.recommendations: List[OptimizationRecommendation] = []

    def add_resource(self, usage: ResourceUsage) -> None:
        """Add resource usage data."""
        self.resources[usage.resource_name] = usage
        self._analyze_resource(usage)

    def _analyze_resource(self, usage: ResourceUsage) -> None:
        """Analyze a resource for optimization opportunities."""
        # Check CPU utilization
        if usage.cpu_usage_percent < self.CPU_UNDERUTILIZED_THRESHOLD:
            self._add_recommendation(
                resource_type=usage.resource_type,
                resource_name=usage.resource_name,
                current_value=f"{usage.cpu_request} cores",
                recommended_value=f"{usage.cpu_request * 0.5} cores",
                potential_savings=self._calculate_cpu_savings(
                    usage, usage.cpu_request * 0.5
                ),
                priority="medium",
                reason=f"CPU underutilized at {usage.cpu_usage_percent:.1f}%",
            )
        elif usage.cpu_usage_percent > self.CPU_OVERUTILIZED_THRESHOLD:
            self._add_recommendation(
                resource_type=usage.resource_type,
                resource_name=usage.resource_name,
                current_value=f"{usage.cpu_request} cores",
                recommended_value=f"{usage.cpu_request * 1.5} cores",
                potential_savings=0,
                priority="high",
                reason=f"CPU overutilized at {usage.cpu_usage_percent:.1f}%",
            )

        # Check memory utilization
        if usage.memory_usage_percent < self.MEMORY_UNDERUTILIZED_THRESHOLD:
            self._add_recommendation(
                resource_type=usage.resource_type,
                resource_name=usage.resource_name,
                current_value=f"{usage.memory_request} GB",
                recommended_value=f"{usage.memory_request * 0.5} GB",
                potential_savings=self._calculate_memory_savings(
                    usage, usage.memory_request * 0.5
                ),
                priority="medium",
                reason=f"Memory underutilized at {usage.memory_usage_percent:.1f}%",
            )
        elif usage.memory_usage_percent > self.MEMORY_OVERUTILIZED_THRESHOLD:
            self._add_recommendation(
                resource_type=usage.resource_type,
                resource_name=usage.resource_name,
                current_value=f"{usage.memory_request} GB",
                recommended_value=f"{usage.memory_request * 1.5} GB",
                potential_savings=0,
                priority="high",
                reason=f"Memory overutilized at {usage.memory_usage_percent:.1f}%",
            )

    def _add_recommendation(
        self,
        resource_type: str,
        resource_name: str,
        current_value: str,
        recommended_value: str,
        potential_savings: float,
        priority: str,
        reason: str,
    ) -> None:
        """Add an optimization recommendation."""
        rec = OptimizationRecommendation(
            resource_type=resource_type,
            resource_name=resource_name,
            current_value=current_value,
            recommended_value=recommended_value,
            potential_savings_usd=potential_savings,
            priority=priority,
            reason=reason,
        )
        self.recommendations.append(rec)
        logger.info(
            f"Recommendation: {resource_name} - {reason} "
            f"(potential savings: ${potential_savings:.2f}/month)"
        )

    def _calculate_cpu_savings(
        self, usage: ResourceUsage, new_cpu: float
    ) -> float:
        """Calculate monthly savings from CPU reduction."""
        cpu_diff = usage.cpu_request - new_cpu
        # Approximate $20/core/month
        return cpu_diff * 20 * 730  # hours per month

    def _calculate_memory_savings(
        self, usage: ResourceUsage, new_memory: float
    ) -> float:
        """Calculate monthly savings from memory reduction."""
        memory_diff = usage.memory_request - new_memory
        # Approximate $5/GB/month
        return memory_diff * 5

    def get_recommendations(
        self, priority: Optional[str] = None
    ) -> List[OptimizationRecommendation]:
        """Get optimization recommendations."""
        if priority:
            return [r for r in self.recommendations if r.priority == priority]
        return self.recommendations

    def get_high_priority_recommendations(self) -> List[OptimizationRecommendation]:
        """Get high priority recommendations."""
        return self.get_recommendations(priority="high")

    def get_potential_savings(self) -> float:
        """Get total potential monthly savings."""
        return sum(r.potential_savings_usd for r in self.recommendations)

    def get_right_size_recommendations(self) -> List[Dict[str, Any]]:
        """Get right-sizing recommendations."""
        return [
            {
                "resource": r.resource_name,
                "type": r.resource_type,
                "current": r.current_value,
                "recommended": r.recommended_value,
                "savings": f"${r.potential_savings_usd:.2f}/month",
                "priority": r.priority,
                "reason": r.reason,
            }
            for r in self.recommendations
        ]


class UnusedResourceDetector:
    """Detect unused or idle resources."""

    def __init__(self):
        """Initialize unused resource detector."""
        self.idle_threshold_days = 7

    def detect_unused_pods(
        self, pod_metrics: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect pods with no activity."""
        unused = []
        for pod in pod_metrics:
            if (
                pod.get("cpu_usage_percent", 0) < 5
                and pod.get("memory_usage_percent", 0) < 5
                and pod.get("network_bytes", 0) < 1000
            ):
                unused.append({
                    "name": pod["name"],
                    "namespace": pod.get("namespace", "default"),
                    "reason": "No CPU, memory, or network activity",
                    "recommendation": "Consider scaling down or removing",
                })
        return unused

    def detect_unused_services(
        self, services: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect services with no endpoints."""
        unused = []
        for service in services:
            if service.get("endpoints_count", 0) == 0:
                unused.append({
                    "name": service["name"],
                    "namespace": service.get("namespace", "default"),
                    "reason": "No endpoints connected",
                    "recommendation": "Verify if service is needed",
                })
        return unused

    def detect_unused_volumes(
        self, volumes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect unattached volumes."""
        unused = []
        for volume in volumes:
            if not volume.get("attached", False):
                unused.append({
                    "name": volume["name"],
                    "size_gb": volume.get("size_gb", 0),
                    "reason": "Volume not attached",
                    "recommendation": "Delete if not needed",
                    "potential_savings": f"${volume.get('size_gb', 0) * 0.1:.2f}/month",
                })
        return unused


def get_resource_optimizer() -> ResourceOptimizer:
    """Get singleton resource optimizer instance."""
    return ResourceOptimizer()
