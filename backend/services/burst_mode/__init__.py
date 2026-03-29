"""
Burst Mode Sub-modules for PARWA.

Contains specialized components for burst mode operations:
- scaler: Resource scaling management
- monitor: Queue depth and performance monitoring
"""

from backend.services.burst_mode.scaler import (
    ResourceScaler,
    ScalingConfig,
    ScalingDirection,
    ScalingType,
    ScalingStatus,
    ScalingEvent,
    ResourceState,
    get_resource_scaler,
    reset_resource_scaler,
)

from backend.services.burst_mode.monitor import (
    BurstModeMonitor,
    MonitorThresholds,
    AlertSeverity,
    MetricType,
    Alert,
    RealtimeMetrics,
    get_burst_mode_monitor,
    reset_burst_mode_monitor,
)

__all__ = [
    # Scaler
    "ResourceScaler",
    "ScalingConfig",
    "ScalingDirection",
    "ScalingType",
    "ScalingStatus",
    "ScalingEvent",
    "ResourceState",
    "get_resource_scaler",
    "reset_resource_scaler",
    # Monitor
    "BurstModeMonitor",
    "MonitorThresholds",
    "AlertSeverity",
    "MetricType",
    "Alert",
    "RealtimeMetrics",
    "get_burst_mode_monitor",
    "reset_burst_mode_monitor",
]
