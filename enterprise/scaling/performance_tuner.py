"""
Performance Tuner Module - Week 52, Builder 2
Performance optimization engine for system tuning
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
import logging
import statistics
import time

logger = logging.getLogger(__name__)


class TuningStatus(Enum):
    """Tuning operation status"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    TUNING = "tuning"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"


class OptimizationType(Enum):
    """Type of optimization"""
    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"
    NETWORK = "network"
    LATENCY = "latency"
    THROUGHPUT = "throughput"


@dataclass
class PerformanceMetric:
    """Performance metric data point"""
    name: str
    value: float
    baseline: Optional[float] = None
    target: Optional[float] = None
    unit: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def improvement(self) -> Optional[float]:
        """Calculate improvement percentage"""
        if self.baseline is None or self.baseline == 0:
            return None
        return ((self.baseline - self.value) / self.baseline) * 100

    @property
    def meets_target(self) -> bool:
        """Check if metric meets target"""
        if self.target is None:
            return True
        return self.value <= self.target


@dataclass
class TuningAction:
    """Tuning action to perform"""
    name: str
    optimization_type: OptimizationType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_improvement: float = 0.0
    priority: int = 100
    applied: bool = False
    result: Optional[str] = None


@dataclass
class TuningResult:
    """Result of a tuning operation"""
    action: TuningAction
    success: bool
    before_value: Optional[float] = None
    after_value: Optional[float] = None
    improvement: Optional[float] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class PerformanceProfile:
    """
    Performance profile for a system component.
    """

    def __init__(self, name: str):
        self.name = name
        self.metrics: Dict[str, List[PerformanceMetric]] = {}
        self.baselines: Dict[str, float] = {}
        self.targets: Dict[str, float] = {}
        self.tuning_history: List[TuningResult] = []

    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
    ) -> PerformanceMetric:
        """Record a performance metric"""
        baseline = self.baselines.get(name)
        target = self.targets.get(name)

        metric = PerformanceMetric(
            name=name,
            value=value,
            baseline=baseline,
            target=target,
            unit=unit,
        )

        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(metric)

        return metric

    def set_baseline(self, name: str, value: float) -> None:
        """Set baseline for a metric"""
        self.baselines[name] = value

    def set_target(self, name: str, value: float) -> None:
        """Set target for a metric"""
        self.targets[name] = value

    def get_current(self, name: str) -> Optional[float]:
        """Get current value of a metric"""
        if name in self.metrics and self.metrics[name]:
            return self.metrics[name][-1].value
        return None

    def get_average(self, name: str, window: int = 10) -> Optional[float]:
        """Get average of recent values"""
        if name not in self.metrics or not self.metrics[name]:
            return None
        values = [m.value for m in self.metrics[name][-window:]]
        return statistics.mean(values) if values else None

    def get_trend(self, name: str) -> str:
        """Get trend direction for a metric"""
        if name not in self.metrics or len(self.metrics[name]) < 5:
            return "unknown"

        values = [m.value for m in self.metrics[name][-10:]]
        if len(values) < 5:
            return "unknown"

        first_half = statistics.mean(values[:len(values)//2])
        second_half = statistics.mean(values[len(values)//2:])

        diff_pct = ((second_half - first_half) / first_half * 100) if first_half else 0

        if diff_pct > 5:
            return "increasing"
        elif diff_pct < -5:
            return "decreasing"
        return "stable"


class PerformanceTuner:
    """
    Main performance tuning engine.
    """

    def __init__(self):
        self.profiles: Dict[str, PerformanceProfile] = {}
        self.actions: List[TuningAction] = []
        self.status = TuningStatus.IDLE
        self._handlers: Dict[str, Callable] = {}
        self._optimization_rules: List[Dict[str, Any]] = []

    def create_profile(self, name: str) -> PerformanceProfile:
        """Create a performance profile"""
        profile = PerformanceProfile(name)
        self.profiles[name] = profile
        logger.info(f"Created performance profile: {name}")
        return profile

    def get_profile(self, name: str) -> Optional[PerformanceProfile]:
        """Get a performance profile"""
        return self.profiles.get(name)

    def add_optimization_rule(
        self,
        name: str,
        condition: Callable[[PerformanceProfile], bool],
        action_factory: Callable[[PerformanceProfile], TuningAction],
        priority: int = 100,
    ) -> None:
        """Add an optimization rule"""
        rule = {
            "name": name,
            "condition": condition,
            "action_factory": action_factory,
            "priority": priority,
        }
        self._optimization_rules.append(rule)
        self._optimization_rules.sort(key=lambda r: r["priority"], reverse=True)

    def register_handler(
        self,
        optimization_type: OptimizationType,
        handler: Callable[[TuningAction], bool],
    ) -> None:
        """Register a handler for an optimization type"""
        self._handlers[optimization_type.value] = handler

    def analyze(self, profile_name: str) -> List[TuningAction]:
        """Analyze a profile and suggest tuning actions"""
        profile = self.get_profile(profile_name)
        if not profile:
            return []

        self.status = TuningStatus.ANALYZING
        suggested_actions = []

        for rule in self._optimization_rules:
            try:
                if rule["condition"](profile):
                    action = rule["action_factory"](profile)
                    suggested_actions.append(action)
            except Exception as e:
                logger.error(f"Rule {rule['name']} failed: {e}")

        self.status = TuningStatus.IDLE
        return suggested_actions

    def apply_tuning(self, action: TuningAction) -> TuningResult:
        """Apply a tuning action"""
        start_time = time.time()
        result = TuningResult(action=action, success=False)

        try:
            handler = self._handlers.get(action.optimization_type.value)
            if handler:
                self.status = TuningStatus.TUNING
                success = handler(action)
                result.success = success
                action.applied = True
                action.result = "success" if success else "failed"
            else:
                result.error = f"No handler for {action.optimization_type.value}"
                logger.warning(result.error)

        except Exception as e:
            result.error = str(e)
            logger.error(f"Tuning action failed: {e}")

        result.duration_ms = (time.time() - start_time) * 1000
        self.status = TuningStatus.COMPLETE if result.success else TuningStatus.FAILED

        # Record in history
        for profile in self.profiles.values():
            profile.tuning_history.append(result)

        return result

    def auto_tune(
        self,
        profile_name: str,
        max_actions: int = 5,
    ) -> List[TuningResult]:
        """Automatically tune a profile"""
        actions = self.analyze(profile_name)
        actions = sorted(actions, key=lambda a: a.priority, reverse=True)[:max_actions]

        results = []
        for action in actions:
            result = self.apply_tuning(action)
            results.append(result)
            if not result.success:
                break

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get tuning statistics"""
        total_actions = sum(
            len(p.tuning_history) for p in self.profiles.values()
        )
        successful = sum(
            1 for p in self.profiles.values()
            for r in p.tuning_history if r.success
        )

        return {
            "status": self.status.value,
            "profiles_count": len(self.profiles),
            "total_tuning_actions": total_actions,
            "successful_actions": successful,
            "success_rate": (successful / total_actions * 100) if total_actions else 0,
            "optimization_rules": len(self._optimization_rules),
        }


class CPUPerformanceTuner(PerformanceTuner):
    """
    CPU-specific performance tuner.
    """

    def __init__(self):
        super().__init__()
        self._setup_cpu_rules()

    def _setup_cpu_rules(self) -> None:
        """Setup CPU-specific optimization rules"""

        # High CPU usage rule
        def high_cpu_condition(profile: PerformanceProfile) -> bool:
            cpu = profile.get_current("cpu_usage")
            return cpu is not None and cpu > 80

        def high_cpu_action(profile: PerformanceProfile) -> TuningAction:
            return TuningAction(
                name="reduce_cpu_load",
                optimization_type=OptimizationType.CPU,
                description="Reduce CPU load by optimizing processes",
                parameters={"action": "optimize_processes"},
                expected_improvement=15.0,
                priority=100,
            )

        self.add_optimization_rule("high_cpu", high_cpu_condition, high_cpu_action, 100)

        # CPU throttling rule
        def cpu_throttle_condition(profile: PerformanceProfile) -> bool:
            throttling = profile.get_current("cpu_throttling")
            return throttling is not None and throttling > 10

        def cpu_throttle_action(profile: PerformanceProfile) -> TuningAction:
            return TuningAction(
                name="reduce_throttling",
                optimization_type=OptimizationType.CPU,
                description="Reduce CPU throttling by adjusting limits",
                parameters={"action": "adjust_limits"},
                expected_improvement=20.0,
                priority=90,
            )

        self.add_optimization_rule("cpu_throttle", cpu_throttle_condition, cpu_throttle_action, 90)


class MemoryPerformanceTuner(PerformanceTuner):
    """
    Memory-specific performance tuner.
    """

    def __init__(self):
        super().__init__()
        self._setup_memory_rules()

    def _setup_memory_rules(self) -> None:
        """Setup memory-specific optimization rules"""

        # High memory usage rule
        def high_memory_condition(profile: PerformanceProfile) -> bool:
            memory = profile.get_current("memory_usage")
            return memory is not None and memory > 85

        def high_memory_action(profile: PerformanceProfile) -> TuningAction:
            return TuningAction(
                name="reduce_memory_usage",
                optimization_type=OptimizationType.MEMORY,
                description="Reduce memory usage by clearing caches",
                parameters={"action": "clear_caches"},
                expected_improvement=20.0,
                priority=100,
            )

        self.add_optimization_rule("high_memory", high_memory_condition, high_memory_action, 100)

        # Memory pressure rule
        def memory_pressure_condition(profile: PerformanceProfile) -> bool:
            pressure = profile.get_current("memory_pressure")
            return pressure is not None and pressure > 70

        def memory_pressure_action(profile: PerformanceProfile) -> TuningAction:
            return TuningAction(
                name="reduce_memory_pressure",
                optimization_type=OptimizationType.MEMORY,
                description="Reduce memory pressure by optimizing allocation",
                parameters={"action": "optimize_allocation"},
                expected_improvement=15.0,
                priority=95,
            )

        self.add_optimization_rule("memory_pressure", memory_pressure_condition, memory_pressure_action, 95)


class LatencyOptimizer(PerformanceTuner):
    """
    Latency-specific performance optimizer.
    """

    def __init__(self):
        super().__init__()
        self._setup_latency_rules()

    def _setup_latency_rules(self) -> None:
        """Setup latency-specific optimization rules"""

        # High latency rule
        def high_latency_condition(profile: PerformanceProfile) -> bool:
            latency = profile.get_current("latency_p95")
            return latency is not None and latency > 500

        def high_latency_action(profile: PerformanceProfile) -> TuningAction:
            return TuningAction(
                name="reduce_latency",
                optimization_type=OptimizationType.LATENCY,
                description="Reduce latency by optimizing request handling",
                parameters={"action": "optimize_requests"},
                expected_improvement=25.0,
                priority=100,
            )

        self.add_optimization_rule("high_latency", high_latency_condition, high_latency_action, 100)

        # Latency variance rule
        def latency_variance_condition(profile: PerformanceProfile) -> bool:
            if "latency" not in profile.metrics:
                return False
            values = [m.value for m in profile.metrics["latency"][-20:]]
            if len(values) < 5:
                return False
            variance = statistics.variance(values) if len(values) > 1 else 0
            return variance > 10000  # High variance

        def latency_variance_action(profile: PerformanceProfile) -> TuningAction:
            return TuningAction(
                name="stabilize_latency",
                optimization_type=OptimizationType.LATENCY,
                description="Stabilize latency by smoothing request distribution",
                parameters={"action": "smooth_distribution"},
                expected_improvement=20.0,
                priority=90,
            )

        self.add_optimization_rule("latency_variance", latency_variance_condition, latency_variance_action, 90)
