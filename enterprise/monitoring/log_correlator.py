"""
Log Correlator Module - Week 53, Builder 4
Cross-system log correlation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class CorrelationType(Enum):
    """Types of log correlation"""
    REQUEST_ID = "request_id"
    TRACE_ID = "trace_id"
    SESSION_ID = "session_id"
    USER_ID = "user_id"
    TIME_WINDOW = "time_window"


@dataclass
class CorrelationKey:
    """Key for correlating logs"""
    key_type: CorrelationType
    key_value: str
    source: str = ""


@dataclass
class CorrelatedGroup:
    """Group of correlated log entries"""
    correlation_id: str
    correlation_type: CorrelationType
    entries: List[Dict[str, Any]] = field(default_factory=list)
    sources: Set[str] = field(default_factory=set)
    time_range: tuple = ("", "")
    entry_count: int = 0

    def add_entry(self, entry: Dict[str, Any]) -> None:
        """Add an entry to the group"""
        self.entries.append(entry)
        self.entry_count = len(self.entries)
        if "source" in entry:
            self.sources.add(entry["source"])


class LogCorrelator:
    """
    Correlates logs across multiple systems.
    """

    def __init__(self, time_window_seconds: int = 60):
        self.time_window = timedelta(seconds=time_window_seconds)
        self.groups: Dict[str, CorrelatedGroup] = {}
        self._correlation_keys: Dict[str, List[CorrelationKey]] = defaultdict(list)

    def extract_correlation_keys(
        self,
        entry: Dict[str, Any],
    ) -> List[CorrelationKey]:
        """Extract correlation keys from a log entry"""
        keys = []

        # Check for request ID
        for field in ["request_id", "requestId", "req_id"]:
            if field in entry.get("extra", {}):
                keys.append(CorrelationKey(
                    key_type=CorrelationType.REQUEST_ID,
                    key_value=entry["extra"][field],
                    source=entry.get("source", ""),
                ))

        # Check for trace ID
        for field in ["trace_id", "traceId", "traceId"]:
            if field in entry.get("extra", {}):
                keys.append(CorrelationKey(
                    key_type=CorrelationType.TRACE_ID,
                    key_value=entry["extra"][field],
                    source=entry.get("source", ""),
                ))

        # Check for session ID
        for field in ["session_id", "sessionId"]:
            if field in entry.get("extra", {}):
                keys.append(CorrelationKey(
                    key_type=CorrelationType.SESSION_ID,
                    key_value=entry["extra"][field],
                    source=entry.get("source", ""),
                ))

        # Check for user ID
        for field in ["user_id", "userId", "user"]:
            if field in entry.get("extra", {}):
                keys.append(CorrelationKey(
                    key_type=CorrelationType.USER_ID,
                    key_value=str(entry["extra"][field]),
                    source=entry.get("source", ""),
                ))

        return keys

    def correlate(
        self,
        entry: Dict[str, Any],
    ) -> Optional[CorrelatedGroup]:
        """Correlate an entry with existing groups"""
        keys = self.extract_correlation_keys(entry)
        if not keys:
            return None

        # Find or create group
        group = None

        for key in keys:
            key_id = f"{key.key_type.value}:{key.key_value}"

            if key_id in self._correlation_keys:
                # Find existing group
                for gid in self._correlation_keys[key_id]:
                    if gid in self.groups:
                        group = self.groups[gid]
                        break

            if group:
                break

        if not group:
            # Create new group
            primary_key = keys[0]
            group = CorrelatedGroup(
                correlation_id=f"{primary_key.key_type.value}:{primary_key.key_value}",
                correlation_type=primary_key.key_type,
            )
            self.groups[group.correlation_id] = group

        # Add entry to group
        group.add_entry(entry)

        # Register all keys
        for key in keys:
            key_id = f"{key.key_type.value}:{key.key_value}"
            if group.correlation_id not in self._correlation_keys[key_id]:
                self._correlation_keys[key_id].append(group.correlation_id)

        # Update time range
        if group.entries:
            timestamps = [
                e.get("timestamp") for e in group.entries
                if isinstance(e.get("timestamp"), datetime)
            ]
            if timestamps:
                group.time_range = (
                    min(timestamps).isoformat(),
                    max(timestamps).isoformat(),
                )

        return group

    def get_group(self, correlation_id: str) -> Optional[CorrelatedGroup]:
        """Get a correlation group by ID"""
        return self.groups.get(correlation_id)

    def get_groups_by_type(
        self,
        correlation_type: CorrelationType,
    ) -> List[CorrelatedGroup]:
        """Get groups by correlation type"""
        return [
            g for g in self.groups.values()
            if g.correlation_type == correlation_type
        ]

    def get_groups_by_source(
        self,
        source: str,
    ) -> List[CorrelatedGroup]:
        """Get groups containing entries from a source"""
        return [
            g for g in self.groups.values()
            if source in g.sources
        ]

    def find_related_groups(
        self,
        correlation_id: str,
    ) -> List[CorrelatedGroup]:
        """Find groups related to a given group"""
        group = self.groups.get(correlation_id)
        if not group:
            return []

        related = []
        for key in self._correlation_keys.values():
            if correlation_id in key:
                for gid in key:
                    if gid != correlation_id and gid in self.groups:
                        related.append(self.groups[gid])

        return related

    def prune_old_groups(
        self,
        max_age_hours: int = 24,
    ) -> int:
        """Remove old correlation groups"""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        to_remove = []

        for gid, group in self.groups.items():
            if group.entries:
                last_entry = group.entries[-1]
                ts = last_entry.get("timestamp")
                if isinstance(ts, datetime) and ts < cutoff:
                    to_remove.append(gid)

        for gid in to_remove:
            del self.groups[gid]
            for key in self._correlation_keys.values():
                if gid in key:
                    key.remove(gid)

        return len(to_remove)

    def get_statistics(self) -> Dict[str, Any]:
        """Get correlation statistics"""
        return {
            "total_groups": len(self.groups),
            "by_type": {
                t.value: len(self.get_groups_by_type(t))
                for t in CorrelationType
            },
            "total_keys": len(self._correlation_keys),
            "average_group_size": (
                sum(g.entry_count for g in self.groups.values()) / len(self.groups)
            ) if self.groups else 0,
        }
