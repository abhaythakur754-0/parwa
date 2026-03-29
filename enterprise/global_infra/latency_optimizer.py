# Latency Optimizer - Week 51 Builder 1
# Latency-based routing optimization

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class OptimizationStrategy(Enum):
    LOWEST_LATENCY = "lowest_latency"
    PERCENTILE_BASED = "percentile_based"
    ADAPTIVE = "adaptive"
    GEOGRAPHIC_PROXIMITY = "geographic_proximity"


@dataclass
class LatencyMeasurement:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_region: str = ""
    target_region: str = ""
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RegionLatency:
    region: str = ""
    avg_latency_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    sample_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)


class LatencyOptimizer:
    """Optimizes routing based on latency measurements"""

    def __init__(self):
        self._measurements: List[LatencyMeasurement] = []
        self._region_latencies: Dict[str, RegionLatency] = {}
        self._strategy: OptimizationStrategy = OptimizationStrategy.LOWEST_LATENCY
        self._latency_threshold_ms: float = 100.0
        self._metrics = {
            "total_measurements": 0,
            "optimizations_applied": 0,
            "routes_changed": 0
        }

    def record_latency(
        self,
        source_region: str,
        target_region: str,
        latency_ms: float
    ) -> LatencyMeasurement:
        """Record a latency measurement"""
        measurement = LatencyMeasurement(
            source_region=source_region,
            target_region=target_region,
            latency_ms=latency_ms
        )
        self._measurements.append(measurement)
        self._metrics["total_measurements"] += 1

        # Update region latency stats
        self._update_region_latency(source_region, target_region, latency_ms)

        return measurement

    def _update_region_latency(
        self,
        source_region: str,
        target_region: str,
        latency_ms: float
    ) -> None:
        """Update region latency statistics"""
        key = f"{source_region}->{target_region}"

        # Get recent measurements for this route
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        route_measurements = [
            m.latency_ms for m in self._measurements
            if m.source_region == source_region
            and m.target_region == target_region
            and m.timestamp >= cutoff
        ]

        if not route_measurements:
            return

        route_measurements.sort()
        n = len(route_measurements)

        self._region_latencies[key] = RegionLatency(
            region=target_region,
            avg_latency_ms=sum(route_measurements) / n,
            p50_ms=route_measurements[int(n * 0.5)],
            p95_ms=route_measurements[int(n * 0.95)] if n > 1 else route_measurements[0],
            p99_ms=route_measurements[int(n * 0.99)] if n > 1 else route_measurements[0],
            sample_count=n
        )

    def get_optimal_region(
        self,
        source_region: str,
        available_regions: List[str]
    ) -> Optional[str]:
        """Get optimal target region based on latency"""
        if not available_regions:
            return None

        if len(available_regions) == 1:
            return available_regions[0]

        region_latencies = []

        for target in available_regions:
            key = f"{source_region}->{target}"
            latency = self._region_latencies.get(key)

            if latency:
                if self._strategy == OptimizationStrategy.LOWEST_LATENCY:
                    score = latency.avg_latency_ms
                elif self._strategy == OptimizationStrategy.PERCENTILE_BASED:
                    score = latency.p95_ms
                elif self._strategy == OptimizationStrategy.ADAPTIVE:
                    score = latency.p95_ms * 0.7 + latency.avg_latency_ms * 0.3
                else:
                    score = latency.avg_latency_ms

                region_latencies.append((target, score))

        if not region_latencies:
            return available_regions[0]

        # Return region with lowest score (best latency)
        return min(region_latencies, key=lambda x: x[1])[0]

    def should_reroute(
        self,
        current_region: str,
        source_region: str,
        available_regions: List[str]
    ) -> bool:
        """Determine if traffic should be re-routed"""
        optimal = self.get_optimal_region(source_region, available_regions)

        if not optimal or optimal == current_region:
            return False

        # Check if optimal region is significantly better
        current_key = f"{source_region}->{current_region}"
        optimal_key = f"{source_region}->{optimal}"

        current_latency = self._region_latencies.get(current_key)
        optimal_latency = self._region_latencies.get(optimal_key)

        if not current_latency or not optimal_latency:
            return False

        # Reroute if improvement is > threshold
        improvement = current_latency.avg_latency_ms - optimal_latency.avg_latency_ms
        return improvement > self._latency_threshold_ms

    def set_strategy(self, strategy: OptimizationStrategy) -> None:
        """Set optimization strategy"""
        self._strategy = strategy

    def get_strategy(self) -> OptimizationStrategy:
        """Get current strategy"""
        return self._strategy

    def set_latency_threshold(self, threshold_ms: float) -> None:
        """Set latency threshold for re-routing"""
        self._latency_threshold_ms = threshold_ms

    def get_latency_threshold(self) -> float:
        """Get latency threshold"""
        return self._latency_threshold_ms

    def get_region_latency(
        self,
        source_region: str,
        target_region: str
    ) -> Optional[RegionLatency]:
        """Get latency stats for a route"""
        key = f"{source_region}->{target_region}"
        return self._region_latencies.get(key)

    def get_all_latencies(self) -> Dict[str, RegionLatency]:
        """Get all region latencies"""
        return self._region_latencies.copy()

    def get_measurements(
        self,
        source_region: Optional[str] = None,
        target_region: Optional[str] = None,
        limit: int = 100
    ) -> List[LatencyMeasurement]:
        """Get latency measurements"""
        measurements = self._measurements

        if source_region:
            measurements = [m for m in measurements if m.source_region == source_region]
        if target_region:
            measurements = [m for m in measurements if m.target_region == target_region]

        return measurements[-limit:]

    def cleanup_old_measurements(self, hours: int = 24) -> int:
        """Remove old measurements"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        initial = len(self._measurements)
        self._measurements = [m for m in self._measurements if m.timestamp >= cutoff]
        return initial - len(self._measurements)

    def get_metrics(self) -> Dict[str, Any]:
        """Get optimizer metrics"""
        return {
            **self._metrics,
            "strategy": self._strategy.value,
            "latency_threshold_ms": self._latency_threshold_ms,
            "tracked_routes": len(self._region_latencies)
        }
