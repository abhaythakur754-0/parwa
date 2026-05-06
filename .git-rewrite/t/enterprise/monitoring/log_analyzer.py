"""
Log Analyzer Module - Week 53, Builder 4
Log analysis engine for monitoring
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern
import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log level enum"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Single log entry"""
    timestamp: datetime
    level: LogLevel
    message: str
    source: str = ""
    logger: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "source": self.source,
        }


@dataclass
class LogPattern:
    """Pattern for log analysis"""
    name: str
    pattern: str
    level: Optional[LogLevel] = None
    count: int = 0
    last_matched: Optional[datetime] = None


@dataclass
class AnalysisResult:
    """Result of log analysis"""
    total_entries: int = 0
    by_level: Dict[str, int] = field(default_factory=dict)
    patterns_matched: Dict[str, int] = field(default_factory=dict)
    errors: List[LogEntry] = field(default_factory=list)
    warnings: List[LogEntry] = field(default_factory=list)
    time_range: tuple = ("", "")
    top_sources: List[tuple] = field(default_factory=list)


class LogAnalyzer:
    """
    Analyzes log entries for patterns and anomalies.
    """

    def __init__(self, max_entries: int = 100000):
        self.max_entries = max_entries
        self.entries: List[LogEntry] = []
        self.patterns: Dict[str, LogPattern] = {}
        self._setup_default_patterns()

    def _setup_default_patterns(self) -> None:
        """Setup default log patterns"""
        self.add_pattern("error_pattern", r"[Ee]rror|[Ee]xception")
        self.add_pattern("warning_pattern", r"[Ww]arning|[Ww]arn")
        self.add_pattern("stack_trace", r"Traceback|at\s+\w+\.\w+")
        self.add_pattern("timeout", r"[Tt]imeout|[Tt]imed out")
        self.add_pattern("connection", r"[Cc]onnection.*[Ff]ailed|[Cc]onnect.*[Ee]rror")

    def add_pattern(
        self,
        name: str,
        pattern: str,
        level: Optional[LogLevel] = None,
    ) -> None:
        """Add a log pattern"""
        self.patterns[name] = LogPattern(
            name=name,
            pattern=pattern,
            level=level,
        )

    def remove_pattern(self, name: str) -> bool:
        """Remove a log pattern"""
        if name in self.patterns:
            del self.patterns[name]
            return True
        return False

    def add_entry(self, entry: LogEntry) -> None:
        """Add a log entry"""
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def add_entries(self, entries: List[LogEntry]) -> None:
        """Add multiple entries"""
        for entry in entries:
            self.add_entry(entry)

    def analyze(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source: Optional[str] = None,
        level: Optional[LogLevel] = None,
    ) -> AnalysisResult:
        """Analyze log entries"""
        entries = self.entries

        # Filter by time range
        if start_time:
            entries = [e for e in entries if e.timestamp >= start_time]
        if end_time:
            entries = [e for e in entries if e.timestamp <= end_time]

        # Filter by source
        if source:
            entries = [e for e in entries if e.source == source]

        # Filter by level
        if level:
            entries = [e for e in entries if e.level == level]

        # Calculate statistics
        result = AnalysisResult(total_entries=len(entries))

        # Count by level
        for entry in entries:
            level_name = entry.level.value
            result.by_level[level_name] = result.by_level.get(level_name, 0) + 1

        # Find errors and warnings
        result.errors = [e for e in entries if e.level == LogLevel.ERROR]
        result.warnings = [e for e in entries if e.level == LogLevel.WARNING]

        # Match patterns
        for pattern_name, pattern in self.patterns.items():
            regex = re.compile(pattern.pattern)
            for entry in entries:
                if regex.search(entry.message):
                    pattern.count += 1
                    pattern.last_matched = entry.timestamp
                    result.patterns_matched[pattern_name] = (
                        result.patterns_matched.get(pattern_name, 0) + 1
                    )

        # Calculate time range
        if entries:
            result.time_range = (
                entries[0].timestamp.isoformat(),
                entries[-1].timestamp.isoformat(),
            )

        # Top sources
        source_counter = Counter(e.source for e in entries)
        result.top_sources = source_counter.most_common(10)

        return result

    def search(
        self,
        query: str,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Search log entries"""
        try:
            regex = re.compile(query, re.IGNORECASE)
            return [
                e for e in self.entries
                if regex.search(e.message)
            ][:limit]
        except re.error:
            return [
                e for e in self.entries
                if query.lower() in e.message.lower()
            ][:limit]

    def get_entries_by_level(
        self,
        level: LogLevel,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Get entries by level"""
        return [
            e for e in self.entries
            if e.level == level
        ][:limit]

    def get_error_rate(self, window_seconds: int = 3600) -> float:
        """Calculate error rate"""
        cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
        recent = [e for e in self.entries if e.timestamp >= cutoff]

        if not recent:
            return 0.0

        errors = sum(1 for e in recent if e.level in [LogLevel.ERROR, LogLevel.CRITICAL])
        return errors / len(recent)

    def clear(self) -> None:
        """Clear all entries"""
        self.entries.clear()
        for pattern in self.patterns.values():
            pattern.count = 0
            pattern.last_matched = None
