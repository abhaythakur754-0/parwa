"""
Metrics Collector for Smart Router A/B Testing
Collects and aggregates metrics for experiments
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics
import logging

logger = logging.getLogger(__name__)


class MetricAggregation(Enum):
    """Metric aggregation types"""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    RATE = "rate"


@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    metric_name: str
    value: float
    variant: str
    experiment_id: str
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedMetric:
    """Aggregated metric result"""
    metric_name: str
    variant: str
    aggregation: MetricAggregation
    value: float
    sample_count: int
    period_start: datetime
    period_end: datetime


class MetricsCollector:
    """
    Collects and aggregates metrics for A/B experiments.
    Supports real-time aggregation and historical analysis.
    """
    
    # Metric definitions
    METRIC_DEFINITIONS = {
        'accuracy': {
            'description': 'Routing accuracy',
            'aggregation': MetricAggregation.AVG,
            'unit': 'percentage',
        },
        'latency': {
            'description': 'Query latency',
            'aggregation': MetricAggregation.AVG,
            'unit': 'milliseconds',
        },
        'cost': {
            'description': 'Query cost',
            'aggregation': MetricAggregation.SUM,
            'unit': 'dollars',
        },
        'satisfaction': {
            'description': 'User satisfaction',
            'aggregation': MetricAggregation.AVG,
            'unit': 'score',
        },
        'conversion': {
            'description': 'Conversion rate',
            'aggregation': MetricAggregation.RATE,
            'unit': 'percentage',
        },
        'error_rate': {
            'description': 'Error rate',
            'aggregation': MetricAggregation.RATE,
            'unit': 'percentage',
        },
    }
    
    # Retention settings
    MAX_POINTS = 100000
    AGGREGATION_WINDOW = 60  # seconds
    
    def __init__(self):
        self._points: List[MetricPoint] = []
        self._aggregated: Dict[str, List[AggregatedMetric]] = {}
        self._real_time: Dict[str, Dict[str, float]] = {}
        self._initialized = True
    
    def collect(
        self,
        metric_name: str,
        value: float,
        variant: str,
        experiment_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MetricPoint:
        """
        Collect a metric data point.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            variant: Experiment variant
            experiment_id: Experiment identifier
            session_id: Session identifier
            metadata: Additional metadata
            
        Returns:
            MetricPoint
        """
        point = MetricPoint(
            timestamp=datetime.now(),
            metric_name=metric_name,
            value=value,
            variant=variant,
            experiment_id=experiment_id,
            session_id=session_id,
            metadata=metadata or {}
        )
        
        self._points.append(point)
        
        # Trim old points
        if len(self._points) > self.MAX_POINTS:
            self._points = self._points[-self.MAX_POINTS:]
        
        # Update real-time metrics
        self._update_real_time(point)
        
        return point
    
    def _update_real_time(self, point: MetricPoint) -> None:
        """Update real-time metrics."""
        key = f"{point.experiment_id}:{point.variant}:{point.metric_name}"
        
        if key not in self._real_time:
            self._real_time[key] = {
                'sum': 0,
                'count': 0,
                'avg': 0,
            }
        
        current = self._real_time[key]
        current['sum'] += point.value
        current['count'] += 1
        current['avg'] = current['sum'] / current['count']
    
    def collect_accuracy_metric(
        self,
        experiment_id: str,
        variant: str,
        session_id: str,
        correct: bool
    ) -> MetricPoint:
        """Collect routing accuracy metric."""
        return self.collect(
            metric_name='accuracy',
            value=1.0 if correct else 0.0,
            variant=variant,
            experiment_id=experiment_id,
            session_id=session_id
        )
    
    def collect_latency_metric(
        self,
        experiment_id: str,
        variant: str,
        session_id: str,
        latency_ms: float
    ) -> MetricPoint:
        """Collect latency metric."""
        return self.collect(
            metric_name='latency',
            value=latency_ms,
            variant=variant,
            experiment_id=experiment_id,
            session_id=session_id
        )
    
    def collect_satisfaction_metric(
        self,
        experiment_id: str,
        variant: str,
        session_id: str,
        satisfied: bool
    ) -> MetricPoint:
        """Collect user satisfaction metric."""
        return self.collect(
            metric_name='satisfaction',
            value=1.0 if satisfied else 0.0,
            variant=variant,
            experiment_id=experiment_id,
            session_id=session_id
        )
    
    def collect_conversion_metric(
        self,
        experiment_id: str,
        variant: str,
        session_id: str,
        converted: bool
    ) -> MetricPoint:
        """Collect conversion metric."""
        return self.collect(
            metric_name='conversion',
            value=1.0 if converted else 0.0,
            variant=variant,
            experiment_id=experiment_id,
            session_id=session_id
        )
    
    def aggregate(
        self,
        experiment_id: str,
        metric_name: str,
        aggregation: MetricAggregation,
        period_hours: int = 24
    ) -> Dict[str, AggregatedMetric]:
        """
        Aggregate metrics for an experiment.
        
        Args:
            experiment_id: Experiment identifier
            metric_name: Metric to aggregate
            aggregation: Aggregation type
            period_hours: Time period
            
        Returns:
            Dict of variant to AggregatedMetric
        """
        cutoff = datetime.now() - timedelta(hours=period_hours)
        
        # Filter points
        points = [
            p for p in self._points
            if p.experiment_id == experiment_id
            and p.metric_name == metric_name
            and p.timestamp >= cutoff
        ]
        
        # Group by variant
        by_variant: Dict[str, List[float]] = {}
        for point in points:
            if point.variant not in by_variant:
                by_variant[point.variant] = []
            by_variant[point.variant].append(point.value)
        
        # Aggregate
        results = {}
        for variant, values in by_variant.items():
            if not values:
                continue
            
            if aggregation == MetricAggregation.SUM:
                value = sum(values)
            elif aggregation == MetricAggregation.AVG:
                value = statistics.mean(values)
            elif aggregation == MetricAggregation.MIN:
                value = min(values)
            elif aggregation == MetricAggregation.MAX:
                value = max(values)
            elif aggregation == MetricAggregation.COUNT:
                value = len(values)
            elif aggregation == MetricAggregation.RATE:
                value = sum(values) / len(values)
            else:
                value = statistics.mean(values)
            
            results[variant] = AggregatedMetric(
                metric_name=metric_name,
                variant=variant,
                aggregation=aggregation,
                value=value,
                sample_count=len(values),
                period_start=cutoff,
                period_end=datetime.now()
            )
        
        return results
    
    def get_real_time_metrics(
        self,
        experiment_id: str
    ) -> Dict[str, Dict[str, float]]:
        """
        Get real-time metrics for an experiment.
        
        Args:
            experiment_id: Experiment identifier
            
        Returns:
            Dict of metric -> variant -> value
        """
        result: Dict[str, Dict[str, float]] = {}
        
        for key, data in self._real_time.items():
            exp_id, variant, metric = key.split(':')
            
            if exp_id != experiment_id:
                continue
            
            if metric not in result:
                result[metric] = {}
            
            result[metric][variant] = data['avg']
        
        return result
    
    def get_efficiency_metrics(
        self,
        experiment_id: str
    ) -> Dict[str, Any]:
        """
        Get cost efficiency metrics.
        
        Args:
            experiment_id: Experiment identifier
            
        Returns:
            Efficiency metrics dict
        """
        cost_by_variant = self.aggregate(
            experiment_id,
            'cost',
            MetricAggregation.SUM
        )
        
        accuracy_by_variant = self.aggregate(
            experiment_id,
            'accuracy',
            MetricAggregation.AVG
        )
        
        efficiency = {}
        
        for variant, cost in cost_by_variant.items():
            accuracy = accuracy_by_variant.get(variant)
            
            if accuracy:
                # Cost per accuracy point
                efficiency[variant] = {
                    'total_cost': cost.value,
                    'accuracy': accuracy.value,
                    'cost_per_accuracy': cost.value / max(accuracy.value, 0.01),
                }
        
        return efficiency
    
    def get_latencies(
        self,
        experiment_id: str,
        variant: Optional[str] = None
    ) -> Dict[str, List[float]]:
        """
        Get latency measurements.
        
        Args:
            experiment_id: Experiment identifier
            variant: Optional variant filter
            
        Returns:
            Dict of variant to latency list
        """
        points = [
            p for p in self._points
            if p.experiment_id == experiment_id
            and p.metric_name == 'latency'
        ]
        
        if variant:
            points = [p for p in points if p.variant == variant]
        
        result: Dict[str, List[float]] = {}
        for point in points:
            if point.variant not in result:
                result[point.variant] = []
            result[point.variant].append(point.value)
        
        return result
    
    def is_initialized(self) -> bool:
        """Check if collector is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            'total_points': len(self._points),
            'metrics_tracked': len(set(p.metric_name for p in self._points)),
            'experiments_tracked': len(set(p.experiment_id for p in self._points)),
        }
