"""
Auto-Rollback System for Agent Lightning.

Automatically detects and recovers from model degradation:
- Drift detection
- Performance monitoring
- Rollback execution (<60 seconds)
- Multi-channel alerts
"""

from agent_lightning.deployment.auto_rollback.drift_detector import (
    DriftDetector,
    DriftType,
    DriftResult,
)
from agent_lightning.deployment.auto_rollback.performance_monitor import (
    PerformanceMonitor,
    MetricBaseline,
    PerformanceAlert,
)
from agent_lightning.deployment.auto_rollback.rollback_executor import (
    RollbackExecutor,
    RollbackConfig,
    RollbackResult,
    RollbackTrigger,
)
from agent_lightning.deployment.auto_rollback.alert_manager import (
    AlertManager,
    AlertSeverity,
    AlertChannel,
    Alert,
)


__all__ = [
    # Drift Detector
    "DriftDetector",
    "DriftType",
    "DriftResult",
    # Performance Monitor
    "PerformanceMonitor",
    "MetricBaseline",
    "PerformanceAlert",
    # Rollback Executor
    "RollbackExecutor",
    "RollbackConfig",
    "RollbackResult",
    "RollbackTrigger",
    # Alert Manager
    "AlertManager",
    "AlertSeverity",
    "AlertChannel",
    "Alert",
]
