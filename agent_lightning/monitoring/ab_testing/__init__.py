"""
A/B Testing Framework for Agent Lightning.

Enables safe model deployment through controlled experiments:
- Traffic splitting (consistent hashing)
- Experiment management
- Metrics collection
- Statistical analysis
"""

from agent_lightning.monitoring.ab_testing.traffic_splitter import (
    TrafficSplitter,
    SplitConfig,
    VariantAssignment,
)
from agent_lightning.monitoring.ab_testing.experiment_manager import (
    ExperimentManager,
    Experiment,
    ExperimentStatus,
    ExperimentConfig,
)
from agent_lightning.monitoring.ab_testing.metrics_collector import (
    MetricsCollector,
    MetricType,
    VariantMetrics,
)
from agent_lightning.monitoring.ab_testing.statistical_analyzer import (
    StatisticalAnalyzer,
    SignificanceResult,
    ConfidenceLevel,
)


__all__ = [
    # Traffic Splitter
    "TrafficSplitter",
    "SplitConfig",
    "VariantAssignment",
    # Experiment Manager
    "ExperimentManager",
    "Experiment",
    "ExperimentStatus",
    "ExperimentConfig",
    # Metrics Collector
    "MetricsCollector",
    "MetricType",
    "VariantMetrics",
    # Statistical Analyzer
    "StatisticalAnalyzer",
    "SignificanceResult",
    "ConfidenceLevel",
]
