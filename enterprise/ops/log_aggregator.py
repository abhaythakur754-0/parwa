# Log Aggregator - Week 50 Builder 2
# Centralized log aggregation

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level: LogLevel = LogLevel.INFO
    message: str = ""
    source: str = ""
    tenant_id: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class LogAggregator:
    """Aggregates logs from multiple sources"""

    def __init__(self, max_entries: int = 100000):
        self._logs: List[LogEntry] = []
        self._max_entries = max_entries
        self._by_level: Dict[LogLevel, List[str]] = {l: [] for l in LogLevel}
        self._metrics = {"total_logs": 0, "by_level": {}, "by_source": {}}

    def log(
        self,
        level: LogLevel,
        message: str,
        source: str = "",
        tenant_id: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> LogEntry:
        """Add a log entry"""
        entry = LogEntry(
            level=level,
            message=message,
            source=source,
            tenant_id=tenant_id,
            context=context or {}
        )

        self._logs.append(entry)
        self._by_level[level].append(entry.id)
        self._metrics["total_logs"] += 1

        level_key = level.value
        self._metrics["by_level"][level_key] = self._metrics["by_level"].get(level_key, 0) + 1

        src_key = source or "unknown"
        self._metrics["by_source"][src_key] = self._metrics["by_source"].get(src_key, 0) + 1

        # Trim if over limit
        if len(self._logs) > self._max_entries:
            removed = self._logs.pop(0)
            self._by_level[removed.level].remove(removed.id)

        return entry

    def debug(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> LogEntry:
        return self.log(LogLevel.CRITICAL, message, **kwargs)

    def get_logs(
        self,
        level: Optional[LogLevel] = None,
        source: Optional[str] = None,
        tenant_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[LogEntry]:
        """Get filtered logs"""
        logs = self._logs

        if level:
            logs = [l for l in logs if l.level == level]
        if source:
            logs = [l for l in logs if l.source == source]
        if tenant_id:
            logs = [l for l in logs if l.tenant_id == tenant_id]
        if since:
            logs = [l for l in logs if l.timestamp >= since]

        return logs[-limit:]

    def get_errors(self, hours: int = 24) -> List[LogEntry]:
        """Get all errors in time range"""
        since = datetime.utcnow() - timedelta(hours=hours)
        return [
            l for l in self._logs
            if l.level in [LogLevel.ERROR, LogLevel.CRITICAL]
            and l.timestamp >= since
        ]

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def clear(self) -> int:
        count = len(self._logs)
        self._logs.clear()
        for level in self._by_level:
            self._by_level[level].clear()
        return count
