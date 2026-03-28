"""
Cross-Region Replication Module.

Handles replication across regions:
- Async replication between regions
- Replication monitoring
- Conflict resolution
- Latency tracking
"""

from .cross_region_replication import CrossRegionReplication
from .replication_monitor import ReplicationMonitor
from .conflict_resolver import ConflictResolver
from .latency_tracker import LatencyTracker

__all__ = [
    "CrossRegionReplication",
    "ReplicationMonitor",
    "ConflictResolver",
    "LatencyTracker",
]

__version__ = "1.0.0"
